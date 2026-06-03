/* eslint-env node */
/* eslint-disable no-useless-escape */
// NOTE: double escapes are needed for file path delimiters in webpack regexes for cross-platform support

const fs = require('fs');
const path = require('path');
const settings = require('./settings');
const buildUtils = require('./build_utils');

/**
 * Recursively scans all template files within a given directory for webpack entry tags.
 * It expects that the first capture group (match[1]) of the regex returns an entry name,
 * e.g. "base/common_entry" or "kit/foo/common_entry"
 *
 * As entries are discovered, they are added to the details object. Also, unique aliases and
 * a list of apps with entries are tracked.
 *
 * @param {string} dir - The directory path where the scanning starts.
 * @param {RegExp} entryRegex - The regex used to find a webpack entry in an HTML file.
 * @param {Object} allAppPaths - A dictionary mapping app keys (either "appName/subAppName" or "appName") to their folder paths.
 * @param {Object} details - The details object to be mutated, formatted as:
 *                           {
 *                             entries: {},
 *                             aliases: {},
 *                             appsWithEntries: [],
 *                           }
 * @param {boolean} isProdMode - True if running in production mode (which affects the output filename).
 */
const scanTemplates = (dir, entryRegex, allAppPaths, details, isProdMode) => {
    if (!fs.existsSync(dir)) {
        return; // some apps have javascript but no templates
    }

    fs.readdirSync(dir).forEach(file => {
        const fullPath = path.join(dir, file);
        const stats = fs.statSync(fullPath);

        if (stats.isDirectory()) {
            // Recurse into subfolders
            scanTemplates(fullPath, entryRegex, allAppPaths, details, isProdMode);
        } else if (stats.isFile() && fullPath.endsWith('.html')) {
            const content = fs.readFileSync(fullPath, 'utf-8');
            let match;

            while ((match = entryRegex.exec(content)) !== null) {
                const entryName = match[1];
                const segments = entryName.split('/');

                // Determine the correct app key (first try "app/subApp", then "app")
                let formattedAppName;
                let entryPathSegments;
                const twoSegKey = segments.length >= 2 ? `${segments[0]}/${segments[1]}` : null;

                if (twoSegKey && allAppPaths.hasOwnProperty(twoSegKey)) {
                    formattedAppName = twoSegKey;
                    entryPathSegments = segments.slice(2);
                } else if (allAppPaths.hasOwnProperty(segments[0])) {
                    formattedAppName = segments[0];
                    entryPathSegments = segments.slice(1);
                } else {
                    throw new Error('\x1b[31m' + `JS Entry not found: {% js_entry "${entryName}" %} in ${fullPath}` + '\x1b[0m');
                }

                const appPath = allAppPaths[formattedAppName];
                if (!appPath) {
                    throw new Error(`App path missing for "${formattedAppName}"`);
                }

                // reconstruct the rest of the path under assets, e.g. "common_entry" or "subdir/foo"
                const entryFileName = entryPathSegments.join('/');
                const fullEntryPath = path.join(appPath, settings.ASSETS_DIR, `${entryFileName}.js`);

                if (!fs.existsSync(fullEntryPath)) {
                    throw new Error('\x1b[31m' + `File not found: ${fullEntryPath}` + '\x1b[0m');
                    continue;
                }

                // record the webpack entry
                details.entries[entryName] = {
                    import: fullEntryPath,
                    filename: isProdMode
                        ? `${entryName}.[contenthash].js`
                        : `${entryName}.js`,
                };

                // create an alias for import resolution
                if (!(formattedAppName in details.aliases)) {
                    details.aliases[formattedAppName] =
                        path.join(appPath, settings.ASSETS_DIR);
                }

                // track which apps actually had entries
                if (!details.appsWithEntries.includes(formattedAppName)) {
                    details.appsWithEntries.push(formattedAppName);
                }
            }
        }
    });
};

/**
 * Generates the webpack entry details for the provided apps.
 *
 * @param {RegExp} entryRegex - The regex for identifying an entry in an HTML page.
 * @param {Object} allAppPaths - A dictionary of app keys ("appName/subAppName" or "appName") to their folder paths.
 * @param {boolean} isProdMode - True if running in production mode.
 *
 * @returns {Object} - An object with the structure:
 *                     {
 *                       entries: {},
 *                       aliases: {},
 *                       appsWithEntries: [],
 *                     }
 */
const getDetails = (entryRegex, allAppPaths, isProdMode) => {
    const details = {
        entries: {},
        aliases: {},
        appsWithEntries: [],
    };

    Object.entries(allAppPaths).forEach(([appKey, appDir]) => {
        scanTemplates(
            path.join(appDir, settings.TEMPLATES_DIR),
            entryRegex,
            allAppPaths,
            details,
            isProdMode,
        );
    });

    return details;
};

// When run from the command line
if (require.main === module) {
    if (!fs.existsSync(settings.BUILD_ARTIFACTS_DIR)) {
        fs.mkdirSync(settings.BUILD_ARTIFACTS_DIR);
    }

    const isProductionMode = process.argv.includes('--prod');
    const allAppPaths = buildUtils.getAllAppPaths();

    // Pre‑seed aliases/apps for always‑include apps (whether "category/app" or just "app")
    const aliases = {};
    const appsWithEntries = [];
    settings.alwaysIncludeApps.forEach(appKey => {
        if (!allAppPaths[appKey]) {
            console.warn(`alwaysIncludeApps key "${appKey}" not found in allAppPaths`);
            return;
        }
        aliases[appKey] = path.join(allAppPaths[appKey], settings.ASSETS_DIR);
        appsWithEntries.push(appKey);
    });

    const defaultDetails = getDetails(
        settings.ENTRY_REGEX,
        allAppPaths,
        isProductionMode,
    );

    fs.writeFileSync(
        settings.DETAILS_PATH,
        JSON.stringify({
            entries: defaultDetails.entries,
            aliases: { ...aliases, ...defaultDetails.aliases },
            appsWithEntries: [...appsWithEntries, ...defaultDetails.appsWithEntries],
            allAppPaths,
        }, null, 2),
    );
}

module.exports = {
    getDetails,
};
