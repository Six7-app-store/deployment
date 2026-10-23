#!/usr/bin/env python3
"""Tests für den Hook-Helfer. Nur Standardbibliothek, kein pytest.

    python harness/test_agent_guard.py        # oder: make harness-test

Warum es diese Tests gibt: Ein Fehler in `agent_guard.py` fällt sonst erst
auf, wenn ein Agent mitten in einer Aufgabe hängt — und dann sieht es aus
wie ein Fehler des Agenten, nicht wie einer des Harness. Geprüft wird die
Pfad- und Entscheidungslogik, nicht Docker: alles, was einen Container
braucht, ist bewusst nicht Teil dieser Tests. `git` kommt genau einmal vor,
in einem Wegwerf-Repo (CommitGateHilfen).
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))

spec = importlib.util.spec_from_file_location(
    "agent_guard", os.path.join(HERE, "agent_guard.py")
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

sync_spec = importlib.util.spec_from_file_location(
    "harness_sync", os.path.join(HERE, "sync.py")
)
sync = importlib.util.module_from_spec(sync_spec)
sync_spec.loader.exec_module(sync)


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


DOT_NAME = "." + "env"


class BashSchutz(unittest.TestCase):
    """Die Shell geht an den Read-deny-Regeln vorbei — der Hook faengt sie."""

    def bash(self, command: str) -> str:
        return capture(guard.bash, {"tool_input": {"command": command}})

    def test_leser_werden_geblockt(self):
        for command in (
            "cat .env",
            "cat deployment/.env",
            "head -5 .env",
            "tail .env.staging",
            "sed -n 1p deployment/.env",
            "base64 backend/keys/tool.pem",
            "python -c \"print(open('.env').read())\"",
            "grep SECRET deployment/.env",
            "docker run --env-file=.env alpine",
        ):
            self.assertIn("deny", self.bash(command), command)

    def test_aufruf_ohne_dateinamen_ist_nicht_hook_sache(self):
        # Der Aufruf, der die aufgeloesten Werte ohne Dateinamen ausgibt,
        # wird bewusst NICHT hier geblockt, sondern von einer deny-Regel in
        # permissions.json. Eine Substring-Suche im Kommandostring wuerde
        # auch jede Erwaehnung treffen -- sie hat beim Bau den eigenen
        # Commit aufgehalten.
        self.assertEqual(self.bash("docker compose config"), "")

    def test_harmlose_kommandos_bleiben_durch(self):
        for command in (
            "cat .env.example",
            "cat deployment/.env.staging.example",
            "make dev-up",
            "docker exec backend-dev poetry run pytest",
            "git status --porcelain",
            "docker compose -f docker-compose.dev.yml ps",
            "cat docs/harness.md",
        ):
            self.assertEqual(self.bash(command), "", command)

    def test_ohne_kommando_keine_entscheidung(self):
        self.assertEqual(capture(guard.bash, {}), "")

    def test_bekannte_luecke_pfad_erst_zur_laufzeit(self):
        # Festgehalten, nicht behoben: ein Pfad, der erst in der Shell
        # entsteht, steht nicht im Kommando und ist so nicht zu finden.
        # Davor schuetzt nur, dass Bash nachfragt, solange nichts in der
        # allow-Liste steht. Wer das hier "reparieren" will, muss zuerst
        # erklaeren, wie er $V aufloest, ohne die Shell zu starten.
        self.assertEqual(self.bash("V=dotenv; cat .$V"), "")

    def test_erwaehnung_wird_mitgeblockt(self):
        # Gewollte Falschmeldung: dieses Kommando liest nichts, nennt den
        # Namen aber. Beim Bau dieses Hooks hat er genau so den eigenen
        # Patch geblockt. Lieber einmal zu viel als ein Geheimnis im Kontext.
        self.assertIn("deny", self.bash("echo bitte die " + DOT_NAME + " pflegen"))


class Zerlegung(unittest.TestCase):
    def test_trennt_an_operatoren_und_zeilen(self):
        self.assertEqual(
            guard.segments("cd backend && git commit -m x\ngit status; ls | wc -l"),
            [["cd", "backend"], ["git", "commit", "-m", "x"], ["git", "status"], ["ls"], ["wc", "-l"]],
        )

    def test_text_in_anfuehrungszeichen_bleibt_ein_wort(self):
        self.assertEqual(guard.segments('echo "git commit; rm x"'), [["echo", "git commit; rm x"]])

    def test_heredoc_mit_apostroph(self):
        befehl = "git add a && git commit -m \"$(cat <<'EOF'\nFix don't break\nEOF\n)\""
        self.assertEqual(guard.segments(befehl)[1][:2], ["git", "commit"])

    def test_kaputtes_quoting_nimmt_die_erste_zeile(self):
        self.assertEqual(guard.segments("git commit -F msg\nit's broken")[0], ["git", "commit", "-F", "msg"])

    def test_programm_nach_zuweisungen_und_pfad(self):
        self.assertEqual(guard.program(["MSYS_NO_PATHCONV=1", "/usr/bin/git", "status"]), ("git", ["status"]))
        self.assertEqual(guard.program(["C:\\Tools\\gh.exe", "pr", "view"]), ("gh", ["pr", "view"]))

    def test_git_unterkommando_mit_c(self):
        self.assertEqual(guard.git_call(["-C", "../worker", "-c", "a=b", "commit", "-m", "x"]), ("commit", "../worker", ["-m", "x"]))


class GhZiel(unittest.TestCase):
    def grund(self, befehl: str) -> str:
        name, args = guard.program(guard.segments(befehl)[0])
        return guard.gh_target_reason(name, args)

    def test_schreiben_ohne_repo_wird_geblockt(self):
        for befehl in ("gh pr create --fill", "gh issue create --title x", "gh label create story"):
            self.assertIn("-R Six7-app-store", self.grund(befehl), befehl)

    def test_six7_ist_erlaubt(self):
        self.assertEqual(self.grund("gh issue create -R Six7-app-store/deployment --title x"), "")
        self.assertEqual(self.grund("gh pr create --repo=six7-app-store/backend --fill"), "")

    def test_dhbw_ist_nie_ziel(self):
        self.assertIn("ausschliesslich", self.grund("gh pr create -R DHBW-AppStore/backend --fill"))

    def test_repo_edit_nimmt_das_repo_als_argument(self):
        self.assertEqual(self.grund("gh repo edit Six7-app-store/deployment --enable-issues"), "")
        self.assertIn("ausschliesslich", self.grund("gh repo edit DHBW-AppStore/deployment --enable-issues"))
        self.assertIn("-R Six7-app-store", self.grund("gh repo edit --enable-issues"))

    def test_lesen_braucht_kein_repo(self):
        for befehl in ("gh pr view 3", "gh issue list", "gh run list --limit 5"):
            self.assertEqual(self.grund(befehl), "", befehl)


class StagingWaechter(unittest.TestCase):
    OK = "gh workflow run staging.yml -R Six7-app-store/deployment --ref develop -f stand=develop -f recreate=false"

    def setUp(self):
        self.original = guard.active_staging_runs
        guard.active_staging_runs = lambda: []

    def tearDown(self):
        guard.active_staging_runs = self.original

    def grund(self, befehl: str) -> str:
        name, args = guard.program(guard.segments(befehl)[0])
        return guard.staging_dispatch_reason(name, args)

    def test_develop_ist_erlaubt(self):
        self.assertEqual(self.grund(self.OK), "")

    def test_main_ist_produktion(self):
        self.assertIn("ADR 0015", self.grund(self.OK.replace("stand=develop", "stand=main")))

    def test_stand_muss_ausdruecklich_dastehen(self):
        self.assertIn("ADR 0015", self.grund("gh workflow run staging.yml -R Six7-app-store/deployment --ref develop"))

    def test_ref_muss_develop_sein(self):
        self.assertIn("--ref develop", self.grund(self.OK.replace("--ref develop", "--ref main")))

    def test_json_eingaben_sind_nicht_pruefbar(self):
        self.assertIn("--json", self.grund(self.OK + " --json"))

    def test_laufender_deploy_blockt(self):
        guard.active_staging_runs = lambda: [{"databaseId": 7, "status": "in_progress"}]
        self.assertIn("#7", self.grund(self.OK))

    def test_unbekannter_laufstatus_blockt(self):
        # Schliessen statt schweigen: ohne Auskunft kein Deploy.
        guard.active_staging_runs = lambda: None
        self.assertIn("nicht feststellen", self.grund(self.OK))

    def test_andere_workflows_gehen_den_waechter_nichts_an(self):
        self.assertEqual(self.grund("gh workflow run ci.yml -R Six7-app-store/backend --ref develop"), "")


class CommitErkennung(unittest.TestCase):
    """Wird das Gate fuer den richtigen Ordner gerufen — und nur dann?"""

    def setUp(self):
        self.aufrufe = []
        self.original = guard.commit_gate
        guard.commit_gate = lambda ordner, args, befehl: self.aufrufe.append(ordner) or ""
        self.cwd = os.path.abspath(os.path.join(os.sep, "ws"))

    def tearDown(self):
        guard.commit_gate = self.original

    def bash(self, befehl: str) -> str:
        return capture(guard.bash, {"cwd": self.cwd, "tool_input": {"command": befehl}})

    def test_cd_davor_zaehlt(self):
        self.bash("cd backend && git add . && git commit -m x")
        self.assertEqual(self.aufrufe, [os.path.join(self.cwd, "backend")])

    def test_minus_c_zaehlt(self):
        self.bash("git -C worker commit -am x")
        self.assertEqual(self.aufrufe, [os.path.join(self.cwd, "worker")])

    def test_erwaehnung_ist_kein_commit(self):
        self.bash('echo "git commit" && git log --grep "git commit"')
        self.assertEqual(self.aufrufe, [])

    def test_trockenlauf_ist_kein_commit(self):
        self.bash("git commit --dry-run")
        self.assertEqual(self.aufrufe, [])

    def test_grund_wird_zur_ablehnung(self):
        guard.commit_gate = lambda ordner, args, befehl: "Tests rot"
        self.assertIn("Tests rot", self.bash("git commit -m x"))

    def test_defektes_gate_schliesst(self):
        def kaputt(*_):
            raise RuntimeError("kaputt")

        guard.commit_gate = kaputt
        ausgabe = json.loads(self.bash("git commit -m x"))["hookSpecificOutput"]
        self.assertEqual(ausgabe["permissionDecision"], "deny")
        self.assertIn("selbst gescheitert", ausgabe["permissionDecisionReason"])


class DokuZuordnung(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        harness = os.path.join(self.root, "deployment", "harness")
        os.makedirs(harness)
        with open(os.path.join(harness, "doc-map.json"), "w", encoding="utf-8") as handle:
            json.dump(
                {"regeln": [{
                    "repo": "backend", "pfade": ["app/models.py", "alembic/versions/*"],
                    "doku": ["docs/architektur.md"], "warum": "Datenmodell",
                }]},
                handle,
            )
        self.beruehrt = set()
        self.original = guard.touched_since_base
        guard.touched_since_base = lambda _: set(self.beruehrt)

    def tearDown(self):
        guard.touched_since_base = self.original
        self.tmp.cleanup()

    def gruende(self, dateien, befehl="git commit -m x", repo="backend"):
        return guard.doc_reasons(repo, self.root, dateien, befehl)

    def test_modell_ohne_doku_wird_gemeldet(self):
        gruende = self.gruende(["app/models.py"])
        self.assertIn("deployment/docs/architektur.md", gruende[0])
        self.assertIn(guard.DOC_ACK, gruende[-1])

    def test_unterordner_passen_aufs_muster(self):
        self.assertTrue(self.gruende(["alembic/versions/2026_10_23-neu.py"]))

    def test_doku_auf_dem_branch_genuegt(self):
        self.beruehrt = {"docs/architektur.md"}
        self.assertEqual(self.gruende(["app/models.py"]), [])

    def test_bestaetigung_in_der_nachricht_genuegt(self):
        befehl = f'git commit -m "x\n\n{guard.DOC_ACK} nur ein Index"'
        self.assertEqual(self.gruende(["app/models.py"], befehl), [])

    def test_fremde_dateien_und_repos_bleiben_still(self):
        self.assertEqual(self.gruende(["app/routers/apps.py"]), [])
        self.assertEqual(self.gruende(["app/models.py"], repo="worker"), [])

    def test_ohne_zuordnungsdatei_still(self):
        self.assertEqual(guard.doc_reasons("backend", os.path.join(self.root, "nix"), ["app/models.py"], ""), [])


class CommitGateHilfen(unittest.TestCase):
    @unittest.skipUnless(shutil.which("git"), "git fehlt")
    def test_ungetrackte_dateien_zaehlen_mit(self):
        # Der Hook laeuft vor `git add -A && git commit`. Eine neue Datei ist
        # in dem Moment ungetrackt — fehlte sie hier, ginge ein Commit aus
        # lauter neuen Dateien ohne Tests durch. Das einzige git in diesen
        # Tests, in einem Wegwerf-Repo.
        with tempfile.TemporaryDirectory() as repo:
            subprocess.run(["git", "init", "-q", repo], check=True)
            with open(os.path.join(repo, "neu.py"), "w", encoding="utf-8") as handle:
                handle.write("x = 1\n")
            self.assertEqual(guard.changed_files(repo), ["neu.py"])

    def test_ausgaben_werden_als_utf8_gelesen(self):
        # Mit text=True dekodiert Python unter Windows als cp1252 und
        # scheitert an Bytes wie 0x8d — still, im Lesethread. Beim ersten
        # Live-Lauf gegen die Container passiert.
        result = subprocess.run(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write('✓ ü'.encode() + bytes([0x8d]))"],
            capture_output=True,
            **guard.TEXT,
        )
        self.assertTrue(result.stdout.startswith("✓ ü"))

    def test_doku_allein_braucht_keine_tests(self):
        self.assertFalse(guard.needs_tests(["README.md", "docs/x.md", ".claude/hooks/agent_guard.py"]))
        self.assertTrue(guard.needs_tests(["README.md", "app/main.py"]))

    def test_mountpfade_werden_vergleichbar(self):
        erwartet = "c:/users/flock/desktop/dhbw_app/backend"
        for pfad in (
            "C:\\Users\\flock\\Desktop\\DHBW_APP\\backend",
            "C:/Users/flock/Desktop/DHBW_APP/backend/",
            "/run/desktop/mnt/host/c/Users/flock/Desktop/DHBW_APP/backend",
            "/c/Users/flock/Desktop/DHBW_APP/backend",
        ):
            self.assertEqual(guard.normalized_dir(pfad), erwartet, pfad)

    def test_jedes_repo_hat_testeintraege(self):
        for repo, config in guard.REPOS.items():
            self.assertIn("tests", config, repo)
            self.assertIn("needs", config, repo)
            if config["container"]:
                self.assertIn(config["container"], config["tests"], repo)


class IacFormatierer(unittest.TestCase):
    def test_tofu_datei_formatiert_tofu(self):
        self.assertEqual(guard.iac_formatter("envs/staging/main.tofu")[0], "tofu")

    def test_tf_datei_wird_nicht_formatiert(self):
        # Seit ADR 0019 gibt es keine Terraform-Dateien mehr; ein verirrtes
        # .tf bekommt kein terraform fmt.
        self.assertIsNone(guard.iac_formatter("envs/moodle/main.tf"))
        self.assertIsNone(guard.iac_formatter("x.tfvars"))

    def test_andere_dateien_gehen_nicht_an_iac(self):
        self.assertIsNone(guard.iac_formatter("app/tasks.py"))
        self.assertIsNone(guard.iac_formatter("tofu/README.md"))

    def test_gate_kennt_nur_den_tofu_baum(self):
        self.assertEqual(dict(guard.IAC_TREES), {"tofu": "tofu"})


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


class GitArbeitsablauf(unittest.TestCase):
    def test_erhaelt_repo_anweisungen_und_ist_idempotent(self):
        existing = "# Repo\n\nLokale Anweisungen.\n"
        result = sync.git_instructions(existing)
        self.assertTrue(result.startswith(existing))
        self.assertEqual(sync.git_instructions(result), result)

    def test_ersetzt_nur_markierten_block(self):
        existing = (
            "Vorher\n" + sync.GIT_RULE_START + "\nAlte Regel\n"
            + sync.GIT_RULE_END + "\nNachher\n"
        )
        result = sync.git_instructions(existing)
        self.assertTrue(result.startswith("Vorher\n"))
        self.assertTrue(result.endswith("\nNachher\n"))
        self.assertNotIn("Alte Regel", result)

    def test_beschaedigte_marker_werden_nicht_ueberschrieben(self):
        with self.assertRaises(ValueError):
            sync.git_instructions("Anweisungen\n" + sync.GIT_RULE_START)

    def test_check_schreibt_nicht_und_sync_erhaelt_claude(self):
        with tempfile.TemporaryDirectory() as base:
            claude = os.path.join(base, "CLAUDE.md")
            with open(claude, "w", encoding="utf-8") as handle:
                handle.write("Eigene Claude-Anweisungen\n")
            changed = []
            sync.sync_instructions(base, True, changed)
            self.assertTrue(changed)
            self.assertFalse(os.path.exists(os.path.join(base, "AGENTS.md")))
            sync.sync_instructions(base, False, [])
            with open(claude, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "Eigene Claude-Anweisungen\n")
            changed = []
            sync.sync_instructions(base, True, changed)
            self.assertEqual(changed, [])

    def test_neue_repos_erhalten_claude_import(self):
        with tempfile.TemporaryDirectory() as base:
            sync.sync_instructions(base, False, [])
            with open(os.path.join(base, "CLAUDE.md"), encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "@AGENTS.md\n")

    def test_regeln_in_allen_vorhandenen_repos_aktuell(self):
        checked = 0
        for repo in sync.INSTRUCTION_REPOS:
            base = os.path.join(sync.ROOT, repo)
            if not os.path.isdir(base):
                continue
            path = os.path.join(base, "AGENTS.md")
            with open(path, encoding="utf-8") as handle:
                content = handle.read()
            self.assertEqual(content, sync.git_instructions(content), path)
            self.assertIn(sync.GIT_RULE_START, content)
            checked += 1
        self.assertGreater(checked, 0)


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
