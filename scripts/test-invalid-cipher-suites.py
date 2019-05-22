# Author: Hubert Kario, (c) 2015
# Released under Gnu GPL v2.0, see LICENSE file for details

from __future__ import print_function
import traceback
import sys
import getopt
from itertools import chain, islice

from tlsfuzzer.runner import Runner
from tlsfuzzer.messages import Connect, ClientHelloGenerator, \
        ClientKeyExchangeGenerator, ChangeCipherSpecGenerator, \
        FinishedGenerator, ApplicationDataGenerator, AlertGenerator, \
        ResetHandshakeHashes, SetMaxRecordSize, pad_handshake
from tlsfuzzer.expect import ExpectServerHello, ExpectCertificate, \
        ExpectServerHelloDone, ExpectChangeCipherSpec, ExpectFinished, \
        ExpectAlert, ExpectApplicationData, ExpectClose

from tlslite.constants import CipherSuite, AlertLevel, AlertDescription, \
        ExtensionType
from tlslite.extensions import TLSExtension
from tlsfuzzer.utils.lists import natural_sort_keys


def help_msg():
    print("Usage: <script-name> [-h hostname] [-p port] [[probe-name] ...]")
    print(" -h hostname    name of the host to run the test against")
    print("                localhost by default")
    print(" -p port        port number to use for connection, 4433 by default")
    print(" probe-name     if present, will run only the probes with given")
    print("                names and not all of them, e.g \"sanity\"")
    print(" -e probe-name  exclude the probe from the list of the ones run")
    print("                may be specified multiple times")
    print(" -n num         only run `num` random tests instead of a full set")
    print("                (excluding \"sanity\" tests)")
    print(" --help         this message")


def main():
    host = "localhost"
    port = 4433
    num_limit = None
    run_exclude = set()

    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "h:p:e:n:", ["help"])
    for opt, arg in opts:
        if opt == '-h':
            host = arg
        elif opt == '-p':
            port = int(arg)
        elif opt == '-e':
            run_exclude.add(arg)
        elif opt == '-n':
            num_limit = int(arg)
        elif opt == '--help':
            help_msg()
            sys.exit(0)
        else:
            raise ValueError("Unknown option: {0}".format(opt))

    if args:
        run_only = set(args)
    else:
        run_only = None

    #
    # Test if client hello with no valid cipher gets rejected
    #

    conversations = {}

    for name, ciphers in [
                          ("NULL_NULL cipher", [0x00]),
                          ("FORTEZZA", range(0x1c,0x1e)),
                          ("Unknown 0x0047", range(0x47, 0x60)),
                          ("EXPORT1024", range(0x60, 0x66)),
                          ("TLS_DHE_DSS_WITH_RC4_128_SHA", [0x66]),
                          ("Unknown 0x006e", range(0x6e, 0x80)),
                          ("GOST", range(0x80, 0x84)),
                          ("Unknown 0x00c6", range(0xc6, 0xff)),
                          ("TLS_EMPTY_RENEGOTIATION_INFO_SCSV", [0xff]),
                          ("Unknown 0x0100", range(0x0100, 0x1001)),
                          ("Unknown 0x2000", range(0x2000, 0x3001)),
                          ("Unknown 0x3000", range(0x3000, 0x4001)),
                          ("Unknown 0x4000", range(0x4000, 0x5001)),
                          ("Unknown 0x5000", range(0x5000, 0x6001)),
                          ("Unknown 0x6000", range(0x6000, 0x7001)),
                          ("Unknown 0x7000", range(0x7000, 0x8001)),
                          ("Unknown 0x8000", range(0x8000, 0x9001)),
                          ("Unknown 0x9000", range(0x9000, 0xa001)),
                          ("Unknown 0xa000", range(0xa000, 0xb001)),
                          ("Unknown 0xb000", range(0xb000, 0xc001)),
                          ("Unknown 0xc0b0", range(0xc0b0, 0xcca8)),
                          ("Unknown 0xccaf", range(0xccaf, 0xd000)),
                          ("Unknown 0xd000", range(0xd000, 0xe001)),
                          ("Unknown 0xe000", range(0xe000, 0xf001)),
                          ("Unknown 0xf000", range(0xf000, 0xffff)),
                          ]:

        conversation = Connect(host, port)
        node = conversation

        node = node.add_child(ClientHelloGenerator(ciphers))
        node = node.add_child(ExpectAlert())
        node.next_sibling = ExpectClose()

        conversations[name] = conversation

    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_EMPTY_RENEGOTIATION_INFO_SCSV]
    node = node.add_child(ClientHelloGenerator(ciphers))
    node = node.add_child(ExpectServerHello())
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerHelloDone())
    node = node.add_child(ClientKeyExchangeGenerator())
    node = node.add_child(ChangeCipherSpecGenerator())
    node = node.add_child(FinishedGenerator())
    node = node.add_child(ExpectChangeCipherSpec())
    node = node.add_child(ExpectFinished())
    node = node.add_child(ApplicationDataGenerator(
        bytearray(b"GET / HTTP/1.0\n\n")))
    node = node.add_child(ExpectApplicationData())
    node = node.add_child(AlertGenerator(AlertLevel.warning,
                                         AlertDescription.close_notify))
    node = node.add_child(ExpectAlert())
    node.next_sibling = ExpectClose()
    conversations["sanity"] = conversation

    # run the conversation
    good = 0
    bad = 0
    failed = []
    if not num_limit:
        num_limit = len(conversations)

    # make sure that sanity test is run first and last
    # to verify that server was running and kept running throughout
    sanity_test = ('sanity', conversations['sanity'])
    ordered_tests = chain([sanity_test],
                          islice(filter(lambda x: x[0] != 'sanity',
                                        conversations.items()), num_limit),
                          [sanity_test])

    for c_name, c_test in ordered_tests:
        if run_only and c_name not in run_only or c_name in run_exclude:
            continue
        print("{0} ...".format(c_name))

        runner = Runner(c_test)

        res = True
        try:
            runner.run()
        except:
            print("Error while processing")
            print(traceback.format_exc())
            res = False

        if res:
            good += 1
            print("OK\n")
        else:
            bad += 1
            failed.append(c_name)

    print("Test end")
    print("successful: {0}".format(good))
    print("failed: {0}".format(bad))
    failed_sorted = sorted(failed, key=natural_sort_keys)
    print("  {0}".format('\n  '.join(repr(i) for i in failed_sorted)))

    if bad > 0:
        sys.exit(1)

if __name__ == "__main__":
    main()
