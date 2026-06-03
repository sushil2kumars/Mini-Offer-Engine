/**
 * Include this module as the entry point to use HTMX and Alpine.js on a page without
 * any additional javascript.
 *
 * e.g.:
 *
 *      {% js_entry "base/common_entry" %}
 *
 * Tips:
 * - Use the `DjangoHtmxActionMixin` to group related HTMX calls and responses as part of one class based view.
 */
import 'styles/looplink.css';
import 'base/common';

import Alpine from 'alpinejs';

Alpine.start();
