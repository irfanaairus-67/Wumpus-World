<div align="center">
  <img src="https://raw.githubusercontent.com/FortAwesome/Font-Awesome/master/svgs/solid/robot.svg" alt="HuntBot Logo" width="100" height="100" style="filter: drop-shadow(0px 0px 10px #a34808);">
  
  # 🏹 Wumpus HuntBot 🛡️
  
  **An autonomous, web-based AI agent that navigates the deadly Wumpus World using pure Propositional Logic and Resolution Refutation!**

  [![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)]()
  [![HTML5](https://img.shields.io/badge/HTML5-E34F26?style=for-the-badge&logo=html5&logoColor=white)]()
  [![CSS3](https://img.shields.io/badge/CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white)]()
  [![Logic](https://img.shields.io/badge/AI-Propositional_Logic-a34808?style=for-the-badge)]()
  
</div>

---

## 🌟 Features

🤖 **True AI Inference** — Agent proves cells safe using a Knowledge Base of CNF clauses.\
🎲 **Dynamic Generation** — Randomly places Wumpus, Pits, and Gold every mission.\
⚔️ **Hunt the Beast** — Tracks the Wumpus's location via stenches and eliminates it with arrows!\
📈 **Live Visualization** — Watch the agent's thought process, resolution proofs, and percepts in real-time.\
⚡ **Zero-Server Architecture** — The entire engine runs in the browser. No backend required!

---

## 🚀 How to Play

It's easier than ever. The entire application has been compiled into a **single, static HTML file**!

1. Open `index1.html` in your web browser.
2. Select your dungeon size (up to 8x8) and the number of pit traps.
3. Click **Launch Mission**.
4. Use **Single Step** or **Auto Execute** to watch the HuntBot conquer the dungeon!

---

## 🌐 Deploy Online (Cloudflare / GitHub Pages)

Because HuntBot requires **no backend server**, hosting it is incredibly fast and 100% free!

1. Upload the `github/` folder contents (`index1.html` and the `static/` folder) to a new GitHub Repository.
2. Connect your repository to **Cloudflare Pages**, **GitHub Pages**, or **Vercel**.
3. It will instantly deploy your game as a fast, globally-available web app!

---

## 🧠 AI Architecture

The HuntBot isn't just randomly guessing; it uses formal mathematical logic!

| Component | Description |
| :--- | :--- |
| **👀 Sensors** | `Stench` → Wumpus nearby, `Breeze` → Pit nearby, `Glitter` → Gold! |
| **📚 Knowledge Base**| Every percept is translated into Conjunctive Normal Form (CNF) clauses. |
| **⚙️ Inference Engine**| Uses **Resolution Refutation**. To prove a cell is `SAFE(r,c)`, the bot assumes `~SAFE(r,c)` and tries to derive a mathematical contradiction. |
| **🧭 Pathfinding**| Uses Breadth-First Search (BFS) restricted *only* to cells proven safe by the KB. |

---

<div align="center">
  <i>"May your arrows fly true, and your knowledge base remain consistent!"</i> 🏆
</div>
