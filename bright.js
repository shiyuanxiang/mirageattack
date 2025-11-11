(function (global) {
    function escapeXml(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function normalizeLines(source) {
        if (!source) return [];
        if (Array.isArray(source)) {
            return source.map(line => String(line).trim()).filter(Boolean);
        }
        return String(source)
            .split(/\r?\n|\|/)
            .map(line => line.trim())
            .filter(Boolean);
    }

    function buildMask(lines, metrics) {
        const width = Math.max(metrics.width, 1);
        const lineHeight = metrics.lineHeight || (metrics.fontSize * 1.4);
        const height = metrics.height || Math.max(lineHeight * lines.length, lineHeight);
        const startY = Math.max((height - lineHeight * (lines.length - 1)) / 2, lineHeight * 0.6);

        const tspans = lines.map((line, idx) => {
            const y = startY + idx * lineHeight;
            return `<tspan x="${width / 2}" y="${y}">${escapeXml(line)}</tspan>`;
        }).join('');

        const svg = `
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${width} ${height}">
                <style>
                    text {
                        font-family: ${metrics.fontFamily};
                        font-size: ${metrics.fontSize}px;
                        font-weight: ${metrics.fontWeight};
                        fill: white;
                    }
                </style>
                <text text-anchor="middle">${tspans}</text>
            </svg>
        `;
        return {
            dataUrl: `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`,
            width,
            height,
        };
    }

    function getMetrics(element) {
        const computed = window.getComputedStyle(element);
        const fontSize = parseFloat(computed.fontSize) || 16;
        let lineHeight = computed.lineHeight;
        lineHeight = lineHeight === 'normal' ? fontSize * 1.4 : parseFloat(lineHeight);

        const rect = element.getBoundingClientRect();
        return {
            fontSize,
            lineHeight,
            fontFamily: computed.fontFamily || "'Arial Black', sans-serif",
            fontWeight: computed.fontWeight || '600',
            width: rect.width || element.offsetWidth || 800,
            height: rect.height || element.offsetHeight || lineHeight * 2,
        };
    }

    function measureContext(font) {
        const canvas = measureContext.canvas || (measureContext.canvas = document.createElement('canvas'));
        const ctx = canvas.getContext('2d');
        ctx.font = font;
        return ctx;
    }

    function wrapLines(text, metrics) {
        const rawLines = String(text).split(/\r?\n/);
        const maxWidth = Math.max(metrics.width - 4, 1);
        const ctx = measureContext(`${metrics.fontWeight} ${metrics.fontSize}px ${metrics.fontFamily}`);
        const result = [];

        rawLines.forEach(rawLine => {
            if (rawLine === '') {
                result.push('');
                return;
            }
            const tokens = /\s/.test(rawLine) ? rawLine.split(/(\s+)/) : Array.from(rawLine);
            let current = '';
            tokens.forEach(token => {
                if (!token) return;
                const tentative = current + token;
                if (ctx.measureText(tentative).width > maxWidth && current.trim().length > 0) {
                    result.push(current);
                    current = token.trimStart();
                } else {
                    current = tentative;
                }
            });
            result.push(current);
        });

        return result.filter(line => line.length || rawLines.includes(''));
    }

    function apply(options = {}) {
        const containerId = options.containerId || 'bright-container';
        const contentId = options.contentId || 'bright-content';
        const container = document.getElementById(containerId);
        const content = document.getElementById(contentId);

        if (!container || !content) {
            console.warn('[BrightMode] container or content not found');
            return;
        }

        const manualLines = normalizeLines(options.textLines);
        let lines = manualLines.slice();

        if (!lines.length) {
            let sourceText = '';
            if (content.dataset.brightText) {
                sourceText = content.dataset.brightText;
            } else if (container.dataset.brightText) {
                sourceText = container.dataset.brightText;
            } else {
                sourceText = content.textContent || '';
            }
            sourceText = sourceText.trim();
            if (!sourceText) {
                console.warn('[BrightMode] no text provided');
                return;
            }
            const metrics = getMetrics(content);
            lines = wrapLines(sourceText, metrics);
            content.textContent = lines.join('\n');
        } else {
            content.textContent = lines.join('\n');
        }

        const metrics = getMetrics(content);

        const { dataUrl, width, height } = buildMask(lines, {
            ...metrics,
            height: metrics.height || metrics.lineHeight * lines.length + metrics.lineHeight,
        });

        content.style.mask = `url("${dataUrl}")`;
        content.style.webkitMask = `url("${dataUrl}")`;
        content.style.maskSize = `${width}px ${height}px`;
        content.style.webkitMaskSize = `${width}px ${height}px`;
        content.style.maskRepeat = 'no-repeat';
        content.style.webkitMaskRepeat = 'no-repeat';
        content.style.maskPosition = 'center';
        content.style.webkitMaskPosition = 'center';
    }

    global.BrightMode = { apply };

    document.addEventListener('DOMContentLoaded', () => {
        if (document.getElementById('bright-container') && document.getElementById('bright-content')) {
            apply();
        }
    });
})(window);
