#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from check_release_abi import main


def release_metadata(tag):
    return {"tag_name": tag, "draft": False, "prerelease": False,
            "assets": [{"name": "WasmEdge-abi-linux-x86_64.json"},
                       {"name": "WasmEdge-abi-linux-x86_64.tar.gz"}]}


class FlowTests(unittest.TestCase):
    def test_required_assets_for_all_recorded_releases(self):
        for mode in ("pr", "release"):
            for tag in ("1.0", "1.1"):
                for index in (0, 1):
                    for duplicate in (False, True):
                        with self.subTest(mode=mode, tag=tag, index=index, duplicate=duplicate):
                            releases = [release_metadata(v) for v in ("1.0", "1.1")]
                            target = next(item for item in releases if item["tag_name"] == tag)
                            name = target["assets"][index]["name"]
                            if duplicate:
                                target["assets"].append({"name": name})
                            else:
                                target["assets"].pop(index)

                            def command(args, **kwargs):
                                if args[0] == "gh":
                                    return json.dumps([releases])
                                if args[1] == "rev-parse":
                                    return "commit"
                                return "1"

                            with patch.object(sys, "argv", ["check", "candidate.so", "1.2", "--mode", mode]), \
                                 patch("check_release_abi.select", return_value=[{"tag": "1.0"}, {"tag": "1.1"}]), \
                                 patch("check_release_abi.subprocess.check_output", side_effect=command), \
                                 patch("check_release_abi.download") as download, \
                                 patch("check_release_abi.subprocess.run") as analyze:
                                with self.assertRaisesRegex(ValueError, "expected exactly one") as error:
                                    main()
                                self.assertIn(tag, str(error.exception))
                                self.assertIn(name, str(error.exception))
                                download.assert_not_called()
                                analyze.assert_not_called()

    def test_multiple_baselines(self):
        for mode in ("pr", "release"):
            for failure in ("none", "old-symbol", "old-type"):
                with self.subTest(mode=mode, failure=failure):
                    downloads = []
                    analyses = []
                    releases = [release_metadata(tag) for tag in ("1.0", "1.1")]

                    def command(args, **kwargs):
                        if args[0] == "gh":
                            return json.dumps([releases])
                        if args[1] == "rev-parse":
                            return args[2].split("/")[-1].split("^")[0]
                        return "1"

                    def download(tag, name, repository, directory):
                        downloads.append((tag, name))
                        path = Path(directory) / name
                        data = {"schema": 1, "version": tag, "commit": tag,
                                "identity": ["ELF64", "little", "DYN (Shared object file)", "x86"],
                                "soname": "lib.so.0", "symbols": [["api", "FUNC"]],
                                "sha256": hashlib.sha256(tag.encode()).hexdigest()}
                        if failure == "old-symbol" and tag == "1.0":
                            data["symbols"].append(["removed", "FUNC"])
                        path.write_text(json.dumps(data) if name.endswith(".json") else tag)
                        return path

                    def analyze(args, **kwargs):
                        tag = Path(args[-2]).read_text()
                        analyses.append(tag)
                        return subprocess.CompletedProcess(args, int(failure == "old-type" and tag == "1.0"))

                    def inspect(path, option):
                        return {"--file-header": "Class: ELF64\nData: little\nType: DYN (Shared object file)\nMachine: x86\n",
                                "--dynamic": "(SONAME) [lib.so.0]",
                                "--dyn-syms": "1: 0001 1 FUNC GLOBAL DEFAULT 1 api"}[option]

                    with patch.object(sys, "argv", ["check", "candidate.so", "1.2", "--mode", mode]), \
                         patch("check_release_abi.select", return_value=[{"tag": "1.0"}, {"tag": "1.1"}]), \
                         patch("check_release_abi.subprocess.check_output", side_effect=command), \
                         patch("check_release_abi.download", side_effect=download), \
                         patch("check_release_abi.readelf", side_effect=inspect), \
                         patch("check_release_abi.library_from_archive", side_effect=lambda a, p: p.write_bytes(a.read_bytes())), \
                         patch("check_release_abi.subprocess.run", side_effect=analyze):
                        expected = failure == "old-symbol" or (failure == "old-type" and mode == "release")
                        self.assertEqual(main(), int(expected))
                    self.assertEqual(analyses, ["1.0", "1.1"] if mode == "release" else ["1.1"])
                    self.assertEqual([tag for tag, name in downloads if name.endswith(".json")], ["1.0", "1.1"])
                    self.assertEqual([tag for tag, name in downloads if name.endswith(".gz")], analyses)

    def test_pr_flow_and_failures(self):
        for mode in ("ok", "missing-marker", "download", "checksum", "analyzer"):
            with self.subTest(mode=mode):
                release = release_metadata("1.0")

                def command(args, **kwargs):
                    if args[0] == "gh":
                        return json.dumps([[release]])
                    if args[1] == "rev-parse":
                        return "commit\n"
                    if args[1] == "ls-tree":
                        return "" if mode == "missing-marker" else "marker"
                    return "1\n"

                def download(tag, name, repository, directory):
                    if mode == "download":
                        raise subprocess.CalledProcessError(1, "gh")
                    path = Path(directory) / name
                    data = {"schema": 1, "version": "1.0", "commit": "commit",
                            "identity": ["ELF64", "little", "DYN (Shared object file)", "x86"],
                            "soname": "lib.so.0", "symbols": [["api", "FUNC"]],
                            "sha256": "bad" if mode == "checksum" else hashlib.sha256(b"ELF").hexdigest()}
                    path.write_text(json.dumps(data))
                    return path

                def readelf(path, option):
                    return {"--file-header": "Class: ELF64\nData: little\nType: DYN (Shared object file)\nMachine: x86\n",
                            "--dynamic": "(SONAME) [lib.so.0]",
                            "--dyn-syms": "1: 0001 1 FUNC GLOBAL DEFAULT 1 api"}[option]

                with patch.object(sys, "argv", ["check", "candidate.so", "1.1"]), \
                     patch("check_release_abi.subprocess.check_output", side_effect=command), \
                     patch("check_release_abi.select", return_value=[{"tag": "1.0"}]), \
                     patch("check_release_abi.download", side_effect=download), \
                     patch("check_release_abi.readelf", side_effect=readelf), \
                     patch("check_release_abi.library_from_archive", side_effect=lambda a, p: p.write_bytes(b"ELF")), \
                     patch("check_release_abi.subprocess.run") as analyze:
                    analyze.return_value.returncode = 2 if mode == "analyzer" else 0
                    if mode in {"missing-marker", "download", "checksum"}:
                        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                            main()
                        analyze.assert_not_called()
                    else:
                        self.assertEqual(main(), int(mode == "analyzer"))
                        analyze.assert_called_once()


if __name__ == "__main__":
    unittest.main()
