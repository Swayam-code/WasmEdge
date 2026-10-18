#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import unittest

from check_release_abi import validate_manifest


class ManifestTests(unittest.TestCase):
    def test_identity_and_symbols(self):
        data = {"schema": 1, "version": "1.0", "commit": "abc",
                "identity": ["ELF64"], "soname": "lib.so.0",
                "symbols": [["api@OLD", "FUNC"]]}
        self.assertEqual(validate_manifest(data, "1.0", "abc", ("ELF64",), "lib.so.0"),
                         {("api@OLD", "FUNC")})
        for key, value in (("commit", "bad"), ("version", "2.0"),
                           ("soname", "lib.so.1"), ("symbols", [])):
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_manifest({**data, key: value}, "1.0", "abc", ("ELF64",), "lib.so.0")


if __name__ == "__main__":
    unittest.main()
