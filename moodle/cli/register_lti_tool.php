<?php
/**
 * Registriert den App Store als externes LTI-1.3-Werkzeug und gibt die fuenf
 * Werte aus, die dessen .env braucht.
 *
 * Aufruf im Container:
 *
 *   docker exec moodle php /var/www/html/local_register_lti_tool.php \
 *       --appstore=https://appstore.<zone>.users.dhbw.site
 *
 * Warum ein Skript und nicht die Oberflaeche: Die Registrierung von Hand
 * bedeutet acht Formularfelder, und die fuenf Werte danach abzuschreiben ist
 * genau die Sorte Handarbeit, bei der sich ein Zeichendreher einschleicht -
 * der dann als "invalid client_id" auftaucht, zwei Ebenen entfernt von der
 * Ursache.
 *
 * Das Skript ist idempotent: ein bereits registriertes Werkzeug mit derselben
 * Basis-URL wird nicht erneut angelegt, sondern nur ausgelesen.
 */

define('CLI_SCRIPT', true);
require(__DIR__ . '/config.php');
// Beides, nicht nur locallib: lti_get_lti_types() steht in lib.php,
// lti_add_type() und lti_get_type() in locallib.php.
require_once($CFG->dirroot . '/mod/lti/lib.php');
require_once($CFG->dirroot . '/mod/lti/locallib.php');
require_once($CFG->libdir . '/clilib.php');

list($options, $unrecognised) = cli_get_params(
    ['appstore' => null, 'api' => null, 'name' => 'DHBW App Store', 'help' => false],
    ['a' => 'appstore', 'h' => 'help']
);

if ($options['help'] || empty($options['appstore'])) {
    cli_writeln("Aufruf: php register_lti_tool.php --appstore=https://<host> [--api=https://<host>/api]");
    exit($options['help'] ? 0 : 1);
}

$basis = rtrim($options['appstore'], '/');

// Die drei Endpunkte des Werkzeugs liegen NICHT unter der Basis-URL, sondern
// hinter dem API-Praefix: Caddy leitet nur /api/* an das Backend und streift
// das Praefix dabei ab (deployment/caddy/Caddyfile). Unter /lti/* liegen die
// Seiten der Vue-Anwendung - dort registriert, holte Moodle als JWKS die
// index.html des Frontends und jeder Launch liefe gegen eine HTML-Seite,
// deren Antwort aussieht wie ein kaputtes Token.
$api = rtrim($options['api'] ?: ($basis . '/api'), '/');

// Die Konfiguration des Werkzeugs. Einmal gebaut und fuer Anlegen wie
// Aktualisieren benutzt - zwei Stellen, die dasselbe beschreiben, sind zwei
// Stellen, die auseinanderlaufen koennen.
$konfig = new stdClass();
$konfig->lti_toolurl         = $api . '/lti/launch';
$konfig->lti_initiatelogin   = $api . '/lti/login';
$konfig->lti_redirectionuris = $api . '/lti/launch';
$konfig->lti_publickeyset    = $api . '/lti/jwks';
$konfig->lti_keytype         = 'JWK_KEYSET';
$konfig->lti_ltiversion      = '1.3.0';
$konfig->lti_coursevisible   = LTI_COURSEVISIBLE_ACTIVITYCHOOSER;
$konfig->lti_sendname        = LTI_SETTING_ALWAYS;
$konfig->lti_sendemailaddr   = LTI_SETTING_ALWAYS;

// Bereits vorhanden?
//
// Verglichen wird gegen die LAUNCH-URL, nicht gegen die Basis: lti_add_type()
// uebernimmt lti_toolurl als baseurl des Typs. Ein Vergleich mit der Basis
// trifft nie zu, und jeder Aufruf legte eine weitere Registrierung an - mit
// einer neuen client_id, wodurch die zuvor verteilte ungueltig wurde.
//
// Mitgeprueft werden zwei ueberholte Schreibweisen, damit eine bestehende
// Registrierung umgezogen statt verdoppelt wird.
$launchurl = $api . '/lti/launch';
$veraltet  = [$basis . '/lti/launch', $basis];
$vorhanden = null;
foreach (lti_get_lti_types() as $t) {
    $b = rtrim($t->baseurl, '/');
    if ($b === $launchurl || in_array($b, $veraltet, true)) {
        $vorhanden = $t;
        break;
    }
}

if ($vorhanden) {
    // Aktualisieren statt neu anlegen: die client_id bleibt erhalten, also
    // muss die .env des App Stores nicht angefasst und nichts neu ausgerollt
    // werden. Zeigen die URLs woanders hin, werden sie hier geradegezogen.
    $typid = $vorhanden->id;
    $typ = lti_get_type($typid);
    $typ->baseurl = $launchurl;
    $konfig->lti_clientid = $typ->clientid;
    lti_update_type($typ, $konfig);
    cli_writeln("Werkzeug existiert bereits (id={$typid}), Konfiguration abgeglichen.");
} else {
    $typ = new stdClass();
    $typ->name       = $options['name'];
    $typ->baseurl    = $launchurl;
    $typ->state      = LTI_TOOL_STATE_CONFIGURED;
    $typ->ltiversion = '1.3.0';
    $typ->clientid   = random_string(24);
    $konfig->lti_clientid = $typ->clientid;

    $typid = lti_add_type($typ, $konfig);
    cli_writeln("Werkzeug angelegt (id={$typid}).");
}

// Zwei Dienste, die lti_add_type() nicht von selbst einschaltet und ohne die
// je eine Haelfte der Anbindung still nichts tut:
//
//   ltiservice_memberships  Moodle gibt die Teilnehmerliste eines Kurses
//                           heraus (NRPS). Fehlt sie, kommt im Launch kein
//                           namesroleservice-Claim an, und "Studiengruppe aus
//                           Moodle anlegen" scheitert mit lti_nrps_unavailable.
//   contentitem             Moodle fragt beim Anlegen einer Aktivitaet, worauf
//                           sie zeigen soll (Deep Linking). Fehlt es, gibt es
//                           keinen Knopf "Inhalt auswaehlen" und jede
//                           Aktivitaet bleibt ungebunden.
//
// Bewusst hier und nicht nur im Anlege-Zweig: ein Werkzeug, das vor dieser
// Aenderung registriert wurde, soll die Dienste durch einen erneuten Aufruf
// bekommen. Sonst muesste man sie auf jeder bestehenden Instanz von Hand
// nachklicken -- genau die Handarbeit, die dieses Skript vermeiden soll.
$dienste = ['ltiservice_memberships' => '1', 'contentitem' => '1'];
foreach ($dienste as $name => $wert) {
    $zeile = $DB->get_record('lti_types_config', ['typeid' => $typid, 'name' => $name]);
    if ($zeile) {
        if ($zeile->value !== $wert) {
            $zeile->value = $wert;
            $DB->update_record('lti_types_config', $zeile);
            cli_writeln("Dienst {$name} eingeschaltet.");
        }
    } else {
        $DB->insert_record('lti_types_config', (object) [
            'typeid' => $typid,
            'name'   => $name,
            'value'  => $wert,
        ]);
        cli_writeln("Dienst {$name} eingeschaltet.");
    }
}

$typ = lti_get_type($typid);
$deployment = $typid;  // Moodle benutzt die Typ-ID als deployment_id.

cli_writeln("");
cli_writeln("# Diese Zeilen gehoeren in die .env des App Stores:");
cli_writeln("LTI_ENABLED=true");
cli_writeln("LTI_PLATFORM_ISSUER=" . $CFG->wwwroot);
cli_writeln("LTI_CLIENT_ID=" . $typ->clientid);
cli_writeln("LTI_DEPLOYMENT_ID=" . $deployment);
cli_writeln("LTI_JWKS_URL=" . $CFG->wwwroot . "/mod/lti/certs.php");
cli_writeln("LTI_AUTH_LOGIN_URL=" . $CFG->wwwroot . "/mod/lti/auth.php");
cli_writeln("LTI_TOKEN_URL=" . $CFG->wwwroot . "/mod/lti/token.php");
