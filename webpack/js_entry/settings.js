/* eslint-env node */
const path = require('path');

const __BASE = path.resolve(__dirname, '../..');
const BUILD_ARTIFACTS_DIR = path.resolve(__BASE, 'webpack/_build');
const DETAILS_PATH = path.join(BUILD_ARTIFACTS_DIR, 'js_entry.json');

const TEMPLATES_DIR = 'templates';
const ASSETS_DIR = 'assets';
const PROJECT_PATH = path.resolve(__BASE, 'looplink/ui');
const BUNDLED_ASSETS_ROOT = path.resolve(__BASE, 'bundled_assets');

const WEBPACK_PATH = path.join(BUNDLED_ASSETS_ROOT, 'webpack');

const ENTRY_REGEX = /{% js_entry ["']([\/\w\-]+)["'] %}/g;

const BASE_APP_NAME = "base";

/**
 * This object is used to define paths for apps that are not in the standard
 * "looplink/ui" structure (rare).
 * 
 * For example, if you have an app that is located at
 * looplink/appname, you can define it here.
 * 
 * "appname" is the key, and the value is the absolute path to the app.
 */
const otherAppPaths = {};

/**
 * Use this list to specify apps that should always be included in the webpack build,
 * regardless of whether they have a templates directory or not.
 * 
 * This is useful for apps that are not in the standard "looplink/ui/appName" structure,
 * or do not have a `js_entry` in their templates.
 */
const alwaysIncludeApps = [
    BASE_APP_NAME,
];


module.exports = {
    alwaysIncludeApps,
    otherAppPaths,
    ASSETS_DIR,
    BUILD_ARTIFACTS_DIR,
    BUNDLED_ASSETS_ROOT,
    DETAILS_PATH,
    ENTRY_REGEX,
    PROJECT_PATH,
    TEMPLATES_DIR,
    WEBPACK_PATH,
    BASE_APP_NAME,
};
