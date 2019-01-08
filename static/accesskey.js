(function() {
    'use strict';

    function handleKeyDown(event) {
        const key = event.key;
        if (key.length != 1) {
            return;
        }
        const lKey = key.toLowerCase(), uKey = key.toUpperCase();
        const element = document.querySelector(`[accesskey=${lKey}], [accesskey=${uKey}]`);
        if (!element) {
            return;
        }
        element.focus();
        element.click();
        event.preventDefault();
        event.stopPropagation();
    }

    document.addEventListener('keydown', handleKeyDown);
})();
