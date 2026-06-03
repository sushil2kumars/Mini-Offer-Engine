export default [
    {
        languageOptions: {
            parserOptions: {
                ecmaVersion: 12, // ES2021 (version 12) syntax
                sourceType: "module",
            },
            globals: {
                window: "readonly",
                document: "readonly",
                navigator: "readonly",
                localStorage: "readonly",
                sessionStorage: "readonly",
                fetch: "readonly",
            },
        },

        rules: {
            "brace-style": ["error", "1tbs", { allowSingleLine: true }],
            camelcase: ["error", { properties: "never" }],
            "comma-dangle": ["error", "always-multiline"],
            curly: "error",
            eqeqeq: "error",
            "func-call-spacing": "error",
            indent: ["warn", 4, { SwitchCase: 1, FunctionDeclaration: { parameters: "first" } }],
            "linebreak-style": ["error", "unix"],
            "key-spacing": "error",
            "keyword-spacing": "error",
            "no-implicit-globals": "error",
            "no-irregular-whitespace": "error",
            "no-new-object": "error",
            "no-regex-spaces": "error",
            "no-throw-literal": "error",
            "no-unneeded-ternary": "error",
            "no-whitespace-before-property": "error",
            "one-var-declaration-per-line": "error",
            "space-before-function-paren": [
                "error",
                { anonymous: "always", named: "never", asyncArrow: "always" },
            ],
            "space-before-blocks": "error",
            "space-in-parens": ["error", "never"],
            "space-infix-ops": "error",
            strict: ["warn", "global"],
        },
    },
];
