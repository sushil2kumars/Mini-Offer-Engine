/* eslint-env node */
const fs = require('fs');
const path = require('path');
const settings = require("./settings");

/**
 * Check whether the given app path contains a 'templates' or 'assets' folder.
 *
 * @param {string} appPath - The path to the app folder.
 * @returns {boolean} - True if either folder exists, false otherwise.
 */
const hasRequiredFolders = appPath => {
    const templatePath = path.resolve(appPath, settings.TEMPLATES_DIR);
    const assetsPath = path.resolve(appPath, settings.ASSETS_DIR);
    return fs.existsSync(templatePath) || fs.existsSync(assetsPath);
};

/**
 * Returns an object mapping "appName" to the absolute path of each app that contains
 * either a 'templates' or 'assets' folder.
 * 
 * Assumes the structure:
 *   looplink/ui/
 *      app1/
 *        templates/
 *        assets/  
 *      app2/
 *        templates/
 *      app3/
 *        assets/
 *      kit1/
 *        subapp1/
 *          templates/
 *          assets/
 *        subapp2/
 *          templates/
 * 
 * This ignores apps with no templates or assets directory.
 *
 * @returns {Object} - A dictionary where each key is "appName" or "appName/subAppName" and the value is the path.
 */

const getAppPaths = () => {
    const paths = {};
    const apps = fs.readdirSync(settings.PROJECT_PATH, { withFileTypes: true })
        .filter(dirEnt => dirEnt.isDirectory());

    apps.forEach(appDir => {
        const appPath = path.resolve(settings.PROJECT_PATH, appDir.name);

        if (hasRequiredFolders(appPath)) {
            paths[appDir.name] = appPath;
        } else {
            // treat the directory as a "kit" / "sub-app" container
            const subApps = fs.readdirSync(appPath, { withFileTypes: true })
                .filter(dirEnt => dirEnt.isDirectory());

            subApps.forEach(subAppDir => {
                const subAppPath = path.resolve(appPath, subAppDir.name);
                if (hasRequiredFolders(subAppPath)) {
                    // Key is "app/subApp"
                    const key = `${appDir.name}/${subAppDir.name}`;
                    paths[key] = subAppPath;
                }
            });
        }
    });

    return paths;
};

const getAllAppPaths = () => ({
    ...getAppPaths(),
    ...settings.otherAppPaths,
});

module.exports = {
    getAllAppPaths,
};
