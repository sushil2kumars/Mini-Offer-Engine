/* eslint-env node */
const path = require('path');
const fs = require('fs');
const settings = require('./settings');

class EntryChunksPlugin {
    /**
     * This custom plugin creates a json file (default manifest.json), which contains
     * all the Webpack Entries (aka Modules) with a list of all the required Chunks
     * needed to properly load that module without javascript errors.
     *
     * Chunks are generated based on Cache Group Chunks, which are chunked by modules
     * and vendors (npm_modules), and contain the common code shared between multiple
     * entry points that can be cached to improve subsequent page load performance.
     *
     * `looplink.django_ext.js_entry.manifest get_webpack_manifest.py`  ingests the manifest.
     * The data used by the `webpack_modules` template tag in `ll_tags` to return
     * a list of modules to load in `web/partials/webpack.html`.
     *
     * @param {Object} options - Optional settings, e.g. { filename: 'custom_manifest.json' }.
     */

    constructor(options = {}) {
        this.options = options;
    }

    apply(compiler) {
        compiler.hooks.emit.tapAsync('EntryChunksPlugin', (compilation, callback) => {
            const manifest = {};
            const cssManifest = {};

            compilation.entrypoints.forEach((entry, entryName) => {
                manifest[entryName] = [];
                cssManifest[entryName] = [];

                entry.chunks.forEach(chunk => {
                    chunk.files.forEach(file => {
                        if (file.endsWith('.js')) {
                            manifest[entryName].push(file);
                        }
                        if (file.endsWith('.css')) {
                            cssManifest[entryName].push(file);
                        }
                    });
                });
            });

            const filename = this.options.filename || 'manifest.json';
            const filenameCss = this.options.filenameCss || 'manifest.css.json';
            const outputPath = path.join(settings.BUILD_ARTIFACTS_DIR, filename);
            const outputPathCss = path.join(settings.BUILD_ARTIFACTS_DIR, filenameCss);
            fs.writeFileSync(outputPath, JSON.stringify(manifest, null, 2));
            fs.writeFileSync(outputPathCss, JSON.stringify(cssManifest, null, 2));
            callback();
        });
    }
}

module.exports = { EntryChunksPlugin };
