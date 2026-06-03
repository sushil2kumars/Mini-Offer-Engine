/* eslint-env node */
const path = require('path');
const utils = require('./js_entry/utils.js');
const plugins = require('./js_entry/plugins.js');
const settings = require("./js_entry/settings");
const MiniCssExtractPlugin = require("mini-css-extract-plugin");

/**
 * Use this to specify shorthand aliases for modules that are used in multiple places.
 */
const aliases = {
    "styles": path.resolve(__dirname, '../styles'),
};


module.exports = {
    entry: utils.getEntries(),

    module: {
        rules: [
            {
                test: /\.css$/i,
                use: [
                    MiniCssExtractPlugin.loader, 
                    "css-loader",
                    {
                        loader: "postcss-loader",
                        options: {
                            postcssOptions: {
                                plugins: [
                                    require("@tailwindcss/postcss"),
                                    require("autoprefixer"),
                                ],
                            },
                        },
                    },
                ],
            },
            {
                test: /\.scss$/i,
                use: [
                    "style-loader",
                    "css-loader",
                    "sass-loader",
                ],
            },
            {
                test: /\.js$/,
                loader: 'babel-loader',
                exclude: /node_modules/,
            },
            {
                test: /\.png/,
                type: 'asset/resource',
            },
        ],
    },

    plugins: [
        new plugins.EntryChunksPlugin(),
        new MiniCssExtractPlugin({
            filename: "[name].css",
            chunkFilename: "[id].css",
        }),
    ],
    stats: "minimal",

    optimization: {
        splitChunks: {
            cacheGroups: utils.getCacheGroups(),
        },
    },

    resolve: {
        alias: utils.getAllAliases(aliases),
    },

    snapshot: {
        managedPaths: [
            /^node_modules\//,
        ],
    },
    mode: 'development',
    devtool: 'eval-cheap-module-source-map',
    output: {
        filename: '[name].js',
        path: settings.WEBPACK_PATH,
        clean: true,
    },
    watchOptions: {
        ignored: [
            '**/node_modules',
            '**/!(*.js|*.css|*.html|*.py)',
            '*.log',
            path.resolve(__dirname, '../node_modules/'),
            path.resolve(__dirname, '../staticfiles/'),
            path.resolve(__dirname, '../bundled_assets/'),
            path.resolve(__dirname, '_build/'),
        ],
    },
};
