<?php
/**
 * Registriert den App Store als externes LTI-1.3-Werkzeug und gibt die fuenf
 * Werte aus, die dessen .env braucht.
 *
 * Aufruf im Container:
 *
 *   docker exec moodle php /opt/bitnami/moodle/local_register_lti_tool.php \
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
require_once($CFG->dirroot . '/mod/lti/locallib.php');
require_once($CFG->libdir . '/clilib.php');

list($options, $unrecognised) = cli_get_params(
    ['appstore' => null, 'name' => 'DHBW App Store', 'help' => false],
    ['a' => 'appstore', 'h' => 'help']
);

if ($options['help'] || empty($options['appstore'])) {
    cli_writeln("Aufruf: php register_lti_tool.php --appstore=https://<host>");
    exit($options['help'] ? 0 : 1);
}

$basis = rtrim($options['appstore'], '/');

// Bereits vorhanden? Dann nichts anlegen, nur ausgeben.
$vorhanden = null;
foreach (lti_get_lti_types() as $typ) {
    if (rtrim($typ->baseurl, '/') === $basis) {
        $vorhanden = $typ;
        break;
    }
}

if ($vorhanden) {
    cli_writeln("Werkzeug existiert bereits (id={$vorhanden->id}), lese Werte aus.");
    $typid = $vorhanden->id;
} else {
    $typ = new stdClass();
    $typ->name         = $options['name'];
    $typ->baseurl      = $basis;
    $typ->state        = LTI_TOOL_STATE_CONFIGURED;
    $typ->ltiversion   = '1.3.0';
    // Die drei Endpunkte des App Stores. Sie muessen zu den Routen passen,
    // die backend/app/routers/lti.py bereitstellt.
    $typ->clientid     = random_string(24);

    $konfig = new stdClass();
    $konfig->lti_toolurl        = $basis . '/lti/launch';
    $konfig->lti_initiatelogin  = $basis . '/lti/login';
    $konfig->lti_redirectionuris = $basis . '/lti/launch';
    $konfig->lti_publickeyset   = $basis . '/lti/jwks';
    $konfig->lti_keytype        = 'JWK_KEYSET';
    $konfig->lti_clientid       = $typ->clientid;
    $konfig->lti_ltiversion     = '1.3.0';
    $konfig->lti_coursevisible  = LTI_COURSEVISIBLE_ACTIVITYCHOOSER;
    $konfig->lti_sendname       = LTI_SETTING_ALWAYS;
    $konfig->lti_sendemailaddr  = LTI_SETTING_ALWAYS;

    $typid = lti_add_type($typ, $konfig);
    cli_writeln("Werkzeug angelegt (id={$typid}).");
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
