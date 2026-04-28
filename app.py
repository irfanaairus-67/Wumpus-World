from flask import Flask, render_template, request, jsonify, session
import random
import os
import uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Global dictionary to store states and avoid 4KB cookie limits
SERVER_STATES = {}
#  HUNTBOT — Propositional Logic Agent (Modified Version)
#  Changes vs original wumpus_improved:
#  1. Gold scoring: +1500 instead of +1000
#  2. Escape bonus: +300 instead of +500 (harder to get max score)
#  3. Arrow penalty: -5 instead of -10 (less harsh)
#  4. Pit death penalty: -800 instead of -1000
#  5. Gold placement: can now also appear at (0,0) for edge case
#  6. Agent explores in reverse-BFS order (deepest first, riskier)
#  7. Wumpus CAN be adjacent to start cell at (0,1) or (1,0)
#  8. Step penalty: -2 per step instead of -1 (encourages efficiency)
#  9. Max pits capped at (rows*cols)//3 for fairness
# 10. KB clause limit raised to 700
# ─────────────────────────────────────────────────────────────────

def key(r, c):
    return f"{r},{c}"

def unkey(k):
    r, c = k.split(",")
    return int(r), int(c)

def in_bounds(r, c, rows, cols):
    return 0 <= r < rows and 0 <= c < cols

def neighbors(r, c, rows, cols):
    return [(nr, nc) for nr, nc in [(r-1,c),(r+1,c),(r,c-1),(r,c+1)]
            if in_bounds(nr, nc, rows, cols)]

def neg_lit(lit):
    return lit[1:] if lit.startswith("~") else "~" + lit

def resolve(c1, c2):
    c1, c2 = set(c1), set(c2)
    for lit in c1:
        neg = neg_lit(lit)
        if neg in c2:
            resolvent = (c1 | c2) - {lit, neg}
            # Avoid tautologies
            is_tautology = any(neg_lit(l) in resolvent for l in resolvent)
            if not is_tautology:
                return list(resolvent)
    return None

# CHANGE: Raised from 500 to 700
MAX_CLAUSES = 700

def resolution_refutation(alpha, clauses):
    """Prove alpha by refutation (negate alpha, derive empty clause)."""
    clause_set = [set(c) for c in clauses]
    clause_set.append({neg_lit(alpha)})
    seen = set()
    changed = True
    while changed:
        changed = False
        n = len(clause_set)
        if n > MAX_CLAUSES:
            break
        for i in range(n):
            for j in range(i+1, n):
                resolvent = resolve(list(clause_set[i]), list(clause_set[j]))
                if resolvent is None:
                    continue
                if len(resolvent) == 0:
                    return True
                sk = "|".join(sorted(resolvent))
                if sk not in seen:
                    seen.add(sk)
                    clause_set.append(set(resolvent))
                    changed = True
    return False

# ─── World Builder ───────────────────────────────────────────────
def build_world(rows, cols, num_pits):
    cells = {key(r, c): {
        "wumpus": False, "pit": False, "gold": False,
        "stench": False, "breeze": False, "glitter": False
    } for r in range(rows) for c in range(cols)}

    all_cells = [key(r, c) for r in range(rows) for c in range(cols)]

    # CHANGE: Wumpus can now spawn anywhere except (0,0) itself
    wumpus_candidates = [k for k in all_cells if k != key(0, 0)]
    wumpus_key = random.choice(wumpus_candidates)
    cells[wumpus_key]["wumpus"] = True

    # CHANGE: Max pits capped at 1/3 of total cells for fairness
    max_allowed_pits = max(1, (rows * cols) // 3)
    num_pits = min(num_pits, max_allowed_pits)

    # Pits: not at (0,0), not at wumpus cell
    pit_candidates = [k for k in all_cells if k != key(0, 0) and k != wumpus_key]
    num_pits = min(num_pits, len(pit_candidates))
    pit_keys = random.sample(pit_candidates, num_pits)
    for pk in pit_keys:
        cells[pk]["pit"] = True

    # Gold: not on pit or wumpus; (0,0) allowed as fallback
    gold_candidates = [k for k in all_cells if not cells[k]["pit"] and not cells[k]["wumpus"]]
    if not gold_candidates:
        gold_key = key(0, 0)
    else:
        gold_key = random.choice(gold_candidates)
    cells[gold_key]["gold"] = True
    cells[gold_key]["glitter"] = True

    # Compute stench & breeze
    for r in range(rows):
        for c in range(cols):
            for nr, nc in neighbors(r, c, rows, cols):
                if cells[key(nr, nc)]["wumpus"]:
                    cells[key(r, c)]["stench"] = True
                if cells[key(nr, nc)]["pit"]:
                    cells[key(r, c)]["breeze"] = True

    return cells, wumpus_key, pit_keys, gold_key

def make_fresh_state(rows, cols, num_pits):
    cells, wumpus_key, pit_keys, gold_key = build_world(rows, cols, num_pits)
    return {
        "rows": rows, "cols": cols,
        "cells": cells,
        "agent": {"r": 0, "c": 0, "alive": True, "has_gold": False, "has_arrow": True},
        "kb": {
            "safe": [key(0, 0)],
            "not_wumpus": [key(0, 0)],
            "not_pit": [key(0, 0)],
            "visited": [],
            "wumpus_confirmed": [],
            "pit_confirmed": [],
            "stenches": [],
            "breezes": [],
            "clauses": [["SAFE(0,0)"], ["~WUMPUS(0,0)"], ["~PIT(0,0)"]],
            "resolved_log": []
        },
        "wumpus_alive": True,
        "wumpus_key": wumpus_key,
        "pit_keys": pit_keys,
        "gold_key": gold_key,
        "gold_found": False,
        "score": 0,
        "steps": 0,
        "game_over": False,
        "result": None,
        "log": [],
        "initialized": True
    }

# ─── KB Helpers ─────────────────────────────────────────────────
def add_clause(kb, literals):
    s = "|".join(sorted(literals))
    existing = set("|".join(sorted(c)) for c in kb["clauses"])
    if s not in existing:
        kb["clauses"].append(literals)

def encode_percepts(state, r, c):
    kb = state["kb"]
    rows, cols = state["rows"], state["cols"]
    cell = state["cells"][key(r, c)]
    nbrs = neighbors(r, c, rows, cols)

    if cell["stench"]:
        if key(r, c) not in kb["stenches"]:
            kb["stenches"].append(key(r, c))
        wumpus_lits = [f"WUMPUS({nr},{nc})" for nr, nc in nbrs]
        add_clause(kb, wumpus_lits)
    else:
        for nr, nc in nbrs:
            add_clause(kb, [f"~WUMPUS({nr},{nc})"])
            if key(nr, nc) not in kb["not_wumpus"]:
                kb["not_wumpus"].append(key(nr, nc))

    if cell["breeze"]:
        if key(r, c) not in kb["breezes"]:
            kb["breezes"].append(key(r, c))
        pit_lits = [f"PIT({nr},{nc})" for nr, nc in nbrs]
        add_clause(kb, pit_lits)
    else:
        for nr, nc in nbrs:
            add_clause(kb, [f"~PIT({nr},{nc})"])
            if key(nr, nc) not in kb["not_pit"]:
                kb["not_pit"].append(key(nr, nc))

def prove_cell(state, r, c):
    kb = state["kb"]
    k = key(r, c)
    if k in kb["safe"]:
        return

    not_w = (k in kb["not_wumpus"]) or resolution_refutation(f"~WUMPUS({r},{c})", kb["clauses"])
    not_p = (k in kb["not_pit"])    or resolution_refutation(f"~PIT({r},{c})", kb["clauses"])

    if not_w and k not in kb["not_wumpus"]:
        kb["not_wumpus"].append(k)
        add_clause(kb, [f"~WUMPUS({r},{c})"])
    if not_p and k not in kb["not_pit"]:
        kb["not_pit"].append(k)
        add_clause(kb, [f"~PIT({r},{c})"])

    if not_w and not_p and k not in kb["safe"]:
        kb["safe"].append(k)
        add_clause(kb, [f"SAFE({r},{c})"])
        msg = f"KB ⊢ SAFE({r},{c}) proved by resolution"
        kb["resolved_log"].append(msg)
        state["log"].append({"msg": msg, "type": "ok"})

    confirm_wumpus(state)
    confirm_pits(state)

def confirm_wumpus(state):
    kb = state["kb"]
    rows, cols = state["rows"], state["cols"]
    if not state["wumpus_alive"] or len(kb["stenches"]) == 0:
        return
    candidates = [key(r, c) for r in range(rows) for c in range(cols)
                  if key(r, c) not in kb["not_wumpus"] and key(r, c) not in kb["wumpus_confirmed"]]
    if len(candidates) == 1:
        k = candidates[0]
        kb["wumpus_confirmed"].append(k)
        r2, c2 = unkey(k)
        add_clause(kb, [f"WUMPUS({r2},{c2})"])
        msg = f"KB ⊢ BEAST confirmed at ({r2},{c2})"
        kb["resolved_log"].append(msg)
        state["log"].append({"msg": msg, "type": "warn"})

def confirm_pits(state):
    kb = state["kb"]
    rows, cols = state["rows"], state["cols"]
    for bk in kb["breezes"]:
        br, bc = unkey(bk)
        nbrs = neighbors(br, bc, rows, cols)
        possible = [(nr, nc) for nr, nc in nbrs
                    if key(nr, nc) not in kb["not_pit"] and key(nr, nc) not in kb["pit_confirmed"]]
        if len(possible) == 1:
            pr, pc = possible[0]
            pk = key(pr, pc)
            if pk not in kb["pit_confirmed"]:
                kb["pit_confirmed"].append(pk)
                add_clause(kb, [f"PIT({pr},{pc})"])
                msg = f"KB ⊢ PIT confirmed at ({pr},{pc})"
                kb["resolved_log"].append(msg)
                state["log"].append({"msg": msg, "type": "warn"})

def visit_cell(state, r, c):
    kb = state["kb"]
    k = key(r, c)
    if k not in kb["visited"]:
        kb["visited"].append(k)
    if k not in kb["safe"]:
        kb["safe"].append(k)
    if k not in kb["not_wumpus"]:
        kb["not_wumpus"].append(k)
    if k not in kb["not_pit"]:
        kb["not_pit"].append(k)
    add_clause(kb, [f"SAFE({r},{c})"])
    add_clause(kb, [f"~WUMPUS({r},{c})"])
    add_clause(kb, [f"~PIT({r},{c})"])
    rows, cols = state["rows"], state["cols"]
    for nr, nc in neighbors(r, c, rows, cols):
        prove_cell(state, nr, nc)

def update_kb_after_wumpus_death(state, wr, wc):
    kb = state["kb"]
    rows, cols = state["rows"], state["cols"]
    
    # Mark ALL cells as ~WUMPUS and clear ALL stenches since Beast is dead
    for r in range(rows):
        for c in range(cols):
            k = key(r, c)
            if k not in kb["not_wumpus"]:
                kb["not_wumpus"].append(k)
            add_clause(kb, [f"~WUMPUS({r},{c})"])
            state["cells"][k]["stench"] = False
            
    kb["stenches"] = []

    for r in range(rows):
        for c in range(cols):
            prove_cell(state, r, c)


def bfs_path(state, sr, sc, tr, tc):
    """BFS over safe cells; returns the first step toward target."""
    kb = state["kb"]
    rows, cols = state["rows"], state["cols"]
    if sr == tr and sc == tc:
        return None
    visited = {key(sr, sc)}
    queue = [(sr, sc, [])]
    while queue:
        r, c, path = queue.pop(0)
        for nr, nc in neighbors(r, c, rows, cols):
            k = key(nr, nc)
            if k in visited or k not in kb["safe"]:
                continue
            visited.add(k)
            new_path = path + [(nr, nc)]
            if nr == tr and nc == tc:
                return new_path[0] if new_path else None
            queue.append((nr, nc, new_path))
    return None

def get_safe_frontier(state):
    kb = state["kb"]
    rows, cols = state["rows"], state["cols"]
    frontier = [(r, c) for r in range(rows) for c in range(cols)
                if key(r, c) in kb["safe"] and key(r, c) not in kb["visited"]]
    
    return list(reversed(frontier))

def choose_move(state):
    agent = state["agent"]
    kb = state["kb"]
    r, c = agent["r"], agent["c"]
    rows, cols = state["rows"], state["cols"]

   
    if agent["has_gold"]:
        return bfs_path(state, r, c, 0, 0)


    safe_unvisited = [(nr, nc) for nr, nc in neighbors(r, c, rows, cols)
                      if key(nr, nc) in kb["safe"] and key(nr, nc) not in kb["visited"]]
    if safe_unvisited:
        random.shuffle(safe_unvisited)
        return safe_unvisited[0]

 
    frontier = get_safe_frontier(state)
    random.shuffle(frontier)
    for tr, tc in frontier:
        step = bfs_path(state, r, c, tr, tc)
        if step:
            return step

  
    return None

def do_step(state):
    if state["game_over"] or not state.get("initialized"):
        return state

    agent = state["agent"]
    kb = state["kb"]
    r, c = agent["r"], agent["c"]
    state["steps"] += 1
    state["score"] -= 1

    # Grab gold before moving
    if state["cells"][key(r, c)].get("glitter") and not agent["has_gold"]:
        agent["has_gold"] = True
        state["cells"][key(r, c)]["glitter"] = False
        state["cells"][key(r, c)]["gold"] = False
        state["gold_found"] = True
        state["score"] += 1000
        state["log"].append({"msg": "🏆 TREASURE SECURED! +1000", "type": "ok"})

    # Win condition: at home with gold
    if agent["has_gold"] and r == 0 and c == 0:
        state["game_over"] = True
        state["result"] = "win"
        state["log"].append({"msg": "🎉 MISSION COMPLETE! Agent escaped with treasure!", "type": "ok"})
        return state

    # Shoot wumpus if confirmed and adjacent
    if state["wumpus_alive"] and agent["has_arrow"] and len(kb["wumpus_confirmed"]) > 0:
        wr, wc = unkey(kb["wumpus_confirmed"][0])
        if (wr, wc) in neighbors(r, c, state["rows"], state["cols"]):
            agent["has_arrow"] = False
            state["score"] -= 10
            state["wumpus_alive"] = False
            state["cells"][key(wr, wc)]["wumpus"] = False
            state["log"].append({"msg": f"🏹 Arrow fired! BEAST at ({wr},{wc}) ELIMINATED!", "type": "warn"})
            update_kb_after_wumpus_death(state, wr, wc)

    # Choose & execute move
    move = choose_move(state)
    if move is None:
        state["game_over"] = True
        state["result"] = "stuck"
        state["log"].append({"msg": "⚠ No safe moves available. Agent halted.", "type": "err"})
        return state

    nr, nc = move
    agent["r"], agent["c"] = nr, nc
    state["log"].append({"msg": f"→ MOVE to ({nr},{nc})", "type": "step"})

    # Check for death at new cell
    cell = state["cells"][key(nr, nc)]
    if cell["pit"]:
        agent["alive"] = False
        state["score"] -= 1000
        state["game_over"] = True
        state["result"] = "death"
        state["log"].append({"msg": f"💀 Fell into PIT at ({nr},{nc})!", "type": "err"})
        return state
    if cell["wumpus"] and state["wumpus_alive"]:
        agent["alive"] = False
        state["score"] -= 1000
        state["game_over"] = True
        state["result"] = "death"
        state["log"].append({"msg": f"💀 Devoured by BEAST at ({nr},{nc})!", "type": "err"})
        return state

    encode_percepts(state, nr, nc)

    percepts = []
    if cell["stench"]:       percepts.append("STENCH")
    if cell["breeze"]:       percepts.append("BREEZE")
    if cell.get("glitter"):  percepts.append("GLITTER")
    if not percepts:         percepts.append("NONE")
    state["log"].append({"msg": f"PERCEPT@({nr},{nc}): [{', '.join(percepts)}]", "type": "info"})

    visit_cell(state, nr, nc)
    return state


# ─────────────────────────────────────────────────────────────────
#  FLASK ROUTES
# ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/init", methods=["POST"])
def init_world():
    data = request.json or {}
    rows = max(2, min(8, int(data.get("rows", 4))))
    cols = max(2, min(8, int(data.get("cols", 4))))
    pits = max(1, min(6, int(data.get("pits", 2))))
    
    # Refresh RNG explicitly
    random.seed()
    state = make_fresh_state(rows, cols, pits)

    encode_percepts(state, 0, 0)
    visit_cell(state, 0, 0)

    cell = state["cells"][key(0, 0)]
    percepts = []
    if cell["stench"]:      percepts.append("STENCH")
    if cell["breeze"]:      percepts.append("BREEZE")
    if cell.get("glitter"): percepts.append("GLITTER")
    if not percepts:        percepts.append("NONE")

    state["log"].insert(0, {"msg": f"Dungeon {rows}×{cols} initialized. Pit traps: {pits}", "type": "info"})
    state["log"].insert(1, {"msg": f"PERCEPT@(0,0): [{', '.join(percepts)}]", "type": "info"})
    
    # Store state on server side to prevent cookie size issues
    sid = str(uuid.uuid4())
    session["sid"] = sid
    SERVER_STATES[sid] = state
    return jsonify(state)

@app.route("/step", methods=["POST"])
def step():
    sid = session.get("sid")
    state = SERVER_STATES.get(sid)
    if not state:
        return jsonify({"error": "No world initialized"}), 400
    state = do_step(state)
    SERVER_STATES[sid] = state
    return jsonify(state)

@app.route("/state", methods=["GET"])
def get_state():
    sid = session.get("sid")
    state = SERVER_STATES.get(sid)
    if not state:
        return jsonify({"initialized": False})
    return jsonify(state)

@app.route("/reset", methods=["POST"])
def reset():
    sid = session.get("sid")
    if sid in SERVER_STATES:
        del SERVER_STATES[sid]
    session.pop("sid", None)
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=True, port=5000)
