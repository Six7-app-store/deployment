#!/usr/bin/env python3
"""Tests für den Hook-Helfer. Nur Standardbibliothek, kein pytest.

    python harness/test_agent_guard.py        # oder: make harness-test

Warum es diese Tests gibt: Ein Fehler in `agent_guard.py` fällt sonst erst
auf, wenn ein Agent mitten in einer Aufgabe hängt — und dann sieht es aus
wie ein Fehler des Agenten, nicht wie einer des Harness. Geprüft wird die
Pfad- und Entscheidungslogik, nicht Docker: alles, was einen Container oder
`git` braucht, ist bewusst nicht Teil dieser Tests.
"""

import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location(
    "agent_guard", os.path.join(HERE, "agent_guard.py")
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def capture(function, *args) -> str:
    """Was der Hook nach stdout schreibt — das ist seine Entscheidung."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        function(*args)
    return buffer.getvalue().strip()


class SecretFiles(unittest.TestCase):
    def test_geheim(self):
        for name in (
            ".env",
            ".env.staging",
            ".env.prod",
            "deployment/.env",
            "backend/keys/tool.pem",
            "a/b/private.key",
        ):
            self.assertTrue(guard.is_secret_file(name), name)

    def test_gepflegte_vorlagen_bleiben_erlaubt(self):
        for name in (
            ".env.example",
            "deployment/.env.example",
            ".env.staging.example",
            ".secrets.template",
            "deploy.local.env.example",
            "app/models.py",
            "README.md",
        ):
            self.assertFalse(guard.is_secret_file(name), name)


class RepoZuordnung(unittest.TestCase):
    root = os.path.join("C:" + os.sep if os.name == "nt" else os.sep, "ws")

    def pfad(self, *teile):
        return os.path.join(self.root, *teile)

    def test_erstes_segment_entscheidet(self):
        self.assertEqual(guard.repo_of(self.pfad("backend", "app", "x.py"), self.root), "backend")
        self.assertEqual(guard.repo_of(self.pfad("worker", "app", "tasks.py"), self.root), "worker")

    def test_gleichnamiger_unterordner_taeuscht_nicht(self):
        # Vor dem Anker-Fix hätte die Rückwärtssuche hier "backend" gefunden
        # und die Datei im falschen Container formatiert.
        pfad = self.pfad("frontend", "src", "backend", "client.ts")
        self.assertEqual(guard.repo_of(pfad, self.root), "frontend")

    def test_ausserhalb_gehoert_zu_keinem_repo(self):
        self.assertEqual(guard.repo_of(self.pfad("sonstwo", "x.py"), self.root), "")
        self.assertEqual(guard.repo_of(os.path.join(self.root, "..", "x.py"), self.root), "")


class PfadAufloesung(unittest.TestCase):
    def test_relativ_wird_am_cwd_aufgeloest(self):
        cwd = os.path.abspath(os.path.join(os.sep, "ws", "backend"))
        self.assertEqual(
            guard.resolve("app/models.py", cwd),
            os.path.join(cwd, "app", "models.py"),
        )

    def test_absolut_bleibt(self):
        absolut = os.path.abspath(os.path.join(os.sep, "ws", "backend", "app", "x.py"))
        self.assertEqual(guard.resolve(absolut, os.sep), absolut)

    def test_leer_bleibt_leer(self):
        self.assertEqual(guard.resolve("", os.sep), "")

    def test_containerpfad(self):
        root = os.path.abspath(os.path.join(os.sep, "ws"))
        pfad = os.path.join(root, "backend", "app", "routers", "apps.py")
        self.assertEqual(guard.container_path(pfad, "backend", root), "/app/app/routers/apps.py")

    def test_containerpfad_ausserhalb_des_repos(self):
        root = os.path.abspath(os.path.join(os.sep, "ws"))
        pfad = os.path.join(root, "frontend", "src", "x.ts")
        self.assertEqual(guard.container_path(pfad, "backend", root), "")


class HookEingabe(unittest.TestCase):
    def test_posttooluse_vor_pretooluse(self):
        data = {
            "tool_response": {"filePath": "/a/post.py"},
            "tool_input": {"file_path": "/a/pre.py"},
        }
        self.assertEqual(guard.edited_path(data), "/a/post.py")

    def test_pretooluse_als_rueckfall(self):
        self.assertEqual(guard.edited_path({"tool_input": {"file_path": "/a/pre.py"}}), "/a/pre.py")

    def test_leeres_json(self):
        self.assertEqual(guard.edited_path({}), "")

    def test_kaputtes_json_ist_kein_absturz(self):
        stdin = sys.stdin
        sys.stdin = io.StringIO("kein json")
        try:
            self.assertEqual(guard.hook_input(), {})
        finally:
            sys.stdin = stdin


class PreEntscheidungen(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.versions = os.path.join(self.root, "backend", "alembic", "versions")
        os.makedirs(self.versions)
        self.bestehend = os.path.join(self.versions, "2025_01_01-abc_init.py")
        with open(self.bestehend, "w", encoding="utf-8") as handle:
            handle.write("# migration\n")

    def tearDown(self):
        self.tmp.cleanup()

    def pre(self, pfad: str) -> str:
        return capture(guard.pre, {"cwd": self.root, "tool_input": {"file_path": pfad}})

    def test_secret_wird_geblockt(self):
        ausgabe = self.pre(os.path.join(self.root, "deployment", ".env"))
        entscheidung = json.loads(ausgabe)["hookSpecificOutput"]
        self.assertEqual(entscheidung["permissionDecision"], "deny")
        self.assertIn(".env.example", entscheidung["permissionDecisionReason"])

    def test_bestehende_migration_wird_geblockt(self):
        entscheidung = json.loads(self.pre(self.bestehend))["hookSpecificOutput"]
        self.assertEqual(entscheidung["permissionDecision"], "deny")
        self.assertIn("revision --autogenerate", entscheidung["permissionDecisionReason"])

    def test_neue_migration_bleibt_erlaubt(self):
        self.assertEqual(self.pre(os.path.join(self.versions, "2026_09_19-neu.py")), "")

    def test_normale_datei_bleibt_erlaubt(self):
        self.assertEqual(self.pre(os.path.join(self.root, "backend", "app", "models.py")), "")

    def test_ohne_pfad_keine_entscheidung(self):
        self.assertEqual(capture(guard.pre, {"cwd": self.root}), "")

    def test_relativer_pfad_wird_erkannt(self):
        # cwd ist das Repo, der Pfad kommt ohne Repo-Segment herein.
        ausgabe = capture(
            guard.pre,
            {
                "cwd": os.path.join(self.root, "backend"),
                "tool_input": {"file_path": os.path.join("alembic", "versions", "2025_01_01-abc_init.py")},
            },
        )
        self.assertIn("deny", ausgabe)


class StopSchleifenschutz(unittest.TestCase):
    def test_zweiter_durchlauf_blockt_nicht(self):
        # Ohne diese Prüfung hängt eine Sitzung an einem Fehler fest, den
        # Claude nicht beheben kann. Der Test darf kein Docker anfassen —
        # deshalb ist stop_hook_active der einzige geprüfte Pfad.
        self.assertEqual(capture(guard.stop, {"stop_hook_active": True, "cwd": os.sep}), "")


class SitzungsOrdner(unittest.TestCase):
    def test_aus_dem_repo_heraus(self):
        cwd = os.path.abspath(os.path.join(os.sep, "ws", "backend"))
        self.assertEqual(guard.session_dirs({"cwd": cwd}), (cwd, os.path.dirname(cwd)))

    def test_aus_dem_arbeitsordner_heraus(self):
        cwd = os.path.abspath(os.path.join(os.sep, "ws"))
        self.assertEqual(guard.session_dirs({"cwd": cwd}), (cwd, cwd))


class VerteilteKopien(unittest.TestCase):
    """Die Kopien in den Repos müssen Zeichen für Zeichen der Quelle entsprechen."""

    def test_kopien_sind_aktuell(self):
        root = os.path.dirname(os.path.dirname(HERE))
        with open(os.path.join(HERE, "agent_guard.py"), encoding="utf-8") as handle:
            quelle = handle.read()

        # In der CI ist nur `deployment` ausgecheckt, am Arbeitsplatz liegen
        # alle vier Repos plus der Arbeitsordner nebeneinander. Geprüft wird,
        # was da ist — fehlende Nachbarrepos sind kein Fehler.
        orte = [root] + [
            os.path.join(root, repo)
            for repo in ("backend", "frontend", "worker", "deployment")
        ]
        geprueft = 0
        for ort in orte:
            if not os.path.isdir(os.path.join(ort, ".claude")):
                continue
            ziel = os.path.join(ort, ".claude", "hooks", "agent_guard.py")
            with open(ziel, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), quelle, f"{ziel}: `make harness-sync` fehlt")
            geprueft += 1
        self.assertGreater(geprueft, 0, "keine einzige verteilte Kopie gefunden")


if __name__ == "__main__":
    unittest.main(verbosity=2)
