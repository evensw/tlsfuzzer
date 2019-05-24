# Author: Hubert Kario, (c) 2016
# Released under Gnu GPL v2.0, see LICENSE file for details

"""Minimal test for verifying DHE_RSA key exchange support"""

from __future__ import print_function
import traceback
import sys
import getopt
from itertools import chain
from random import sample

from tlsfuzzer.runner import Runner
from tlsfuzzer.messages import Connect, ClientHelloGenerator, \
        ClientKeyExchangeGenerator, ChangeCipherSpecGenerator, \
        FinishedGenerator, ApplicationDataGenerator, AlertGenerator
from tlsfuzzer.expect import ExpectServerHello, ExpectCertificate, \
        ExpectServerHelloDone, ExpectChangeCipherSpec, ExpectFinished, \
        ExpectAlert, ExpectClose, ExpectServerKeyExchange, \
        ExpectApplicationData
from tlslite.constants import CipherSuite, AlertLevel, AlertDescription, \
        ExtensionType, GroupName
from tlslite.extensions import SupportedGroupsExtension
from tlsfuzzer.utils.lists import natural_sort_keys


def help_msg():
    print("Usage: <script-name> [-h hostname] [-p port] [[probe-name] ...]")
    print(" -h hostname    name of the host to run the test against")
    print("                localhost by default")
    print(" -p port        port number to use for connection, 4433 by default")
    print(" --alert name   the expected alert description when no overlap")
    print("                between groups - insufficient_security by default")
    print("                as per RFC 7919, while there is an erratum removing")
    print("                this restriction")
    print(" probe-name     if present, will run only the probes with given")
    print("                names and not all of them, e.g \"sanity\"")
    print(" -e probe-name  exclude the probe from the list of the ones run")
    print("                may be specified multiple times")
    print(" -n num         only run `num` random tests instead of a full set")
    print("                (excluding \"sanity\" tests)")
    print(" --help         this message")


def main():
    """Test if server supports the RFC 7919 key exchange"""
    host = "localhost"
    port = 4433
    num_limit = None
    fatal_alert = "insufficient_security"
    run_exclude = set()

    argv = sys.argv[1:]
    opts, args = getopt.getopt(argv, "h:p:e:n:", ["help", "alert="])
    for opt, arg in opts:
        if opt == '-h':
            host = arg
        elif opt == '-p':
            port = int(arg)
        elif opt == '-e':
            run_exclude.add(arg)
        elif opt == '-n':
            num_limit = int(arg)
        elif opt == '--alert':
            fatal_alert = arg
        elif opt == '--help':
            help_msg()
            sys.exit(0)
        else:
            raise ValueError("Unknown option: {0}".format(opt))

    if args:
        run_only = set(args)
    else:
        run_only = None

    conversations = {}

    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions={ExtensionType.
                                                   renegotiation_info:None}))
    node = node.add_child(ExpectServerHello(extensions={ExtensionType.
                                                     renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
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
    node = node.add_child(ExpectAlert(AlertLevel.warning,
                                      AlertDescription.close_notify))
    node.next_sibling = ExpectClose()
    node.add_child(ExpectClose())

    conversations["sanity"] = conversation

    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions={ExtensionType.
                                                   renegotiation_info:None}))
    node = node.add_child(ExpectServerHello(cipher=CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA,
                                            extensions={ExtensionType.
                                                     renegotiation_info:None}))
    node = node.add_child(ExpectCertificate())
    node = node.add_child(ExpectServerKeyExchange())
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
    node = node.add_child(ExpectAlert(AlertLevel.warning,
                                      AlertDescription.close_notify))
    node.next_sibling = ExpectClose()
    node.add_child(ExpectClose())

    conversations["Check if DHE preferred"] = conversation

    for group in GroupName.allFF:
        conversation = Connect(host, port)
        node = conversation
        ciphers = [CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
        ext = {ExtensionType.renegotiation_info: None}
        ext[ExtensionType.supported_groups] = \
                SupportedGroupsExtension().create([group])
        node = node.add_child(ClientHelloGenerator(ciphers,
                                                   extensions=ext))
        node = node.add_child(ExpectServerHello(extensions={ExtensionType.
            renegotiation_info:None}))
        node = node.add_child(ExpectCertificate())
        node = node.add_child(ExpectServerKeyExchange(valid_groups=[group]))
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
        node = node.add_child(ExpectAlert(AlertLevel.warning,
                                          AlertDescription.close_notify))
        node.next_sibling = ExpectClose()
        node.add_child(ExpectClose())

        conversations["{0} negotiation".format(GroupName.toStr(group))] = \
                conversation

        conversation = Connect(host, port)
        node = conversation
        ciphers = [CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
        ext = {ExtensionType.renegotiation_info: None}
        ext[ExtensionType.supported_groups] = \
                SupportedGroupsExtension().create([511, group])
        node = node.add_child(ClientHelloGenerator(ciphers,
                                                   extensions=ext))
        node = node.add_child(ExpectServerHello(extensions={ExtensionType.
            renegotiation_info:None}))
        node = node.add_child(ExpectCertificate())
        node = node.add_child(ExpectServerKeyExchange(valid_groups=[group]))
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
        node = node.add_child(ExpectAlert(AlertLevel.warning,
                                          AlertDescription.close_notify))
        node.next_sibling = ExpectClose()
        node.add_child(ExpectClose())

        conversations["unassigned tolerance, {0} negotiation".format(GroupName.toStr(group))] = \
                conversation

        conversation = Connect(host, port)
        node = conversation
        ciphers = [CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
        ext = {ExtensionType.renegotiation_info: None}
        ext[ExtensionType.supported_groups] = \
                SupportedGroupsExtension().create([GroupName.secp256r1, group])
        node = node.add_child(ClientHelloGenerator(ciphers,
                                                   extensions=ext))
        node = node.add_child(ExpectServerHello(extensions={ExtensionType.
            renegotiation_info:None}))
        node = node.add_child(ExpectCertificate())
        node = node.add_child(ExpectServerKeyExchange(valid_groups=[group]))
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
        node = node.add_child(ExpectAlert(AlertLevel.warning,
                                          AlertDescription.close_notify))
        node.next_sibling = ExpectClose()
        node.add_child(ExpectClose())

        conversations["tolerate ECC curve in groups without ECC cipher, "
                      "negotiate {0} ".format(GroupName.toStr(group))] = \
                conversation

        for group2 in GroupName.allFF:
            if group == group2:
                continue
            conversation = Connect(host, port)
            node = conversation
            ciphers = [CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
            ext = {ExtensionType.renegotiation_info: None}
            ext[ExtensionType.supported_groups] = \
                    SupportedGroupsExtension().create([511, group, group2])
            node = node.add_child(ClientHelloGenerator(ciphers,
                                                       extensions=ext))
            node = node.add_child(ExpectServerHello(extensions={ExtensionType.
                renegotiation_info:None}))
            node = node.add_child(ExpectCertificate())
            node = node.add_child(ExpectServerKeyExchange(
                valid_groups=[group, group2]))
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
            node = node.add_child(ExpectAlert(AlertLevel.warning,
                                              AlertDescription.close_notify))
            node.next_sibling = ExpectClose()
            node.add_child(ExpectClose())

            conversations["{0} or {1} negotiation".format(GroupName.toStr(group),
                    GroupName.toStr(group2))] = conversation

    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    ext = {ExtensionType.renegotiation_info: None}
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create([511])
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(cipher=CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA,
                                            extensions={ExtensionType.
                                                     renegotiation_info:None}))
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
    node = node.add_child(ExpectAlert(AlertLevel.warning,
                                      AlertDescription.close_notify))
    node.next_sibling = ExpectClose()
    node.add_child(ExpectClose())

    conversations["fallback to non-ffdhe"] = conversation

    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    ext = {ExtensionType.renegotiation_info: None}
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create([GroupName.secp256r1, 511])
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectServerHello(cipher=CipherSuite.TLS_RSA_WITH_AES_128_CBC_SHA,
                                            extensions={ExtensionType.
                                                     renegotiation_info:None}))
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
    node = node.add_child(ExpectAlert(AlertLevel.warning,
                                      AlertDescription.close_notify))
    node.next_sibling = ExpectClose()
    node.add_child(ExpectClose())

    conversations["fallback to non-ffdhe with secp256r1 advertised"] = conversation

    # first paragraph of section 4 in RFC 7919
    conversation = Connect(host, port)
    node = conversation
    ciphers = [CipherSuite.TLS_RSA_WITH_NULL_SHA,
               CipherSuite.TLS_DHE_RSA_WITH_AES_128_CBC_SHA]
    ext = {ExtensionType.renegotiation_info: None}
    ext[ExtensionType.supported_groups] = \
            SupportedGroupsExtension().create([511])
    node = node.add_child(ClientHelloGenerator(ciphers,
                                               extensions=ext))
    node = node.add_child(ExpectAlert(AlertLevel.fatal,
                                      getattr(AlertDescription, fatal_alert)))
    node.add_child(ExpectClose())

    conversations["no overlap between groups"] = conversation


    good = 0
    bad = 0
    failed = []
    num_limit = num_limit or len(conversations)

    # make sure that sanity test is run first and last
    # to verify that server was running and kept running throughout
    sanity_tests = [('sanity', conversations['sanity'])]
    regular_tests = [(k, v) for k, v in conversations.items() if k != 'sanity']
    sampled_tests = sample(regular_tests, min(num_limit, len(regular_tests)))
    ordered_tests = chain(sanity_tests, sampled_tests, sanity_tests)

    for c_name, c_test in ordered_tests:
        if run_only and c_name not in run_only or c_name in run_exclude:
            continue
        print("{0} ...".format(c_name))

        runner = Runner(c_test)

        res = True
        try:
            runner.run()
        except Exception:
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
