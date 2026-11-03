// renderer/index.html から、ブラウザで見る用の preview.html（Artifact 公開用）を作る
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..");
const src = fs.readFileSync(path.join(root, "renderer", "index.html"), "utf8");
const body = src.split("<!--BODY-START-->")[1].split("<!--BODY-END-->")[0];
const out = `<title>BALL 使用感プレビュー</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Zen+Kaku+Gothic+New:wght@400;500;700;900&family=IBM+Plex+Mono:wght@400;600&display=swap">
<link rel="stylesheet" href="styles.css">
${body}
<script src="data.js"></script>
<script src="app.js"></script>
`;
fs.writeFileSync(path.join(root, "renderer", "preview.html"), out);
console.log("wrote renderer/preview.html");
