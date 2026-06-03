/**
 * DO NOT include this module as a `js_entry` point!
 * Use `web/js/common_entry` for default entry points.
 * 
 * Entry points with page-specific javascript should ALWAYS import this module as a dpendency.
 * See `web/js/common_entry.js` for an example starting point.
 * 
 *   For instance:
 * 
 *     import 'web/js/common';
 *     import Alpine from 'alpinejs';
 * 
 *     ... other imports
 *     ... alpine initialization
 *   
 *     Alpine.start();
 */

import 'base/htmx/csrf_token';
import 'base/htmx/dj_hx_action';
