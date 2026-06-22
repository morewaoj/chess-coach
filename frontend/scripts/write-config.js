const fs = require("fs");

const apiBase = process.env.CHESS_COACH_API_BASE || "";

const config = `window.CHESS_COACH_CONFIG = {
  API_BASE: ${JSON.stringify(apiBase)}
};
`;

fs.writeFileSync("config.js", config);
console.log(`Wrote config.js with API_BASE=${apiBase || "(empty)"}`);
