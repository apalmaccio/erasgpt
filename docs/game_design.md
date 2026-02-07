# Game Design Document: Eras Zombie Invasion

## 1. High-Level Concept
**Eras Zombie Invasion** is a standalone RTS for up to 8 players. Players command one of eight nations while fending off escalating AI-controlled zombie hordes. Nations compete for dominance but are incentivized to cooperate against the undead threat. Victory can be achieved by eliminating rival nations or by surviving a late-game zombie onslaught and completing a final evacuation objective.

## 2. Core Pillars
1. **Tension Between Cooperation and Competition**
   - Players must balance expansion and rivalry while responding to shared zombie threats.
2. **Distinct Nations With Readable Roles**
   - Each nation has unique bonuses, units, and tech tree branches.
3. **Escalating AI Threat**
   - Zombies evolve through phases, introducing new unit types, abilities, and behaviors.
4. **RTS Depth With Approachability**
   - Clear resource loops, tech progression, and strong visual/readability cues.

## 3. Game Mode Overview
- **Players:** 2–8
- **Match Length:** 45–75 minutes
- **Map Size:** Large (supports multiple expansion zones, 2–3 zombie nests)
- **Victory Conditions:**
  - Domination (last surviving nation), **or**
  - Joint survival + evacuation objective after final zombie phase.

## 4. Nations (8 Playable Factions)
Each nation includes: an economic bonus, a military identity, and a unique “Legacy Tech” tree branch.

1. **Aurelian Dominion**
   - **Bonus:** Faster research speed.
   - **Identity:** Heavy infantry + siege.
   - **Legacy Tech:** “Imperial Edicts” (buffs to unit discipline and supply).

2. **Verdant Circle**
   - **Bonus:** More efficient food production.
   - **Identity:** Beast tamers and regenerative units.
   - **Legacy Tech:** “Nature’s Concord” (healing auras, rapid territory regrowth).

3. **Ironclad Compact**
   - **Bonus:** Cheaper fortifications.
   - **Identity:** Defensive structures and slow armored troops.
   - **Legacy Tech:** “Bastion Protocols” (structure upgrades and turret specials).

4. **Skyforge Union**
   - **Bonus:** Reduced unit training time.
   - **Identity:** Mechanical units and artillery.
   - **Legacy Tech:** “Aether Engines” (prototype vehicles and drone scouts).

5. **Crimson Choir**
   - **Bonus:** Higher mana generation.
   - **Identity:** Blood magic casters and debuffers.
   - **Legacy Tech:** “Hemomancy” (life-drain and sacrificial economy tools).

6. **Ashen Freeholds**
   - **Bonus:** Increased worker carry capacity.
   - **Identity:** Rapid expansion and ranged skirmishers.
   - **Legacy Tech:** “Frontier Cartels” (trade routes, neutral camp pacts).

7. **Obsidian Covenant**
   - **Bonus:** Cheaper unit upgrades.
   - **Identity:** Elite assassins and stealth raids.
   - **Legacy Tech:** “Shadow Compacts” (mobility and sabotage tech).

8. **Tideborne Assembly**
   - **Bonus:** Reduced naval unit cost (if map includes water zones).
   - **Identity:** Control of waterways and amphibious units.
   - **Legacy Tech:** “Deepcall Rites” (summons and vision in fog).

## 5. Economy & Resources
**Primary Resources**
- **Gold:** Gathered from mines. Used for units/buildings.
- **Lumber:** Harvested from forests. Used for structures and upgrades.
- **Food (Supply):** Produced by farms/settlements. Controls unit cap.
- **Arcana:** Rare resource gained from relics or tech buildings. Enables elite units/abilities.

**Economy Loop**
1. Build workers → gather Gold/Lumber.
2. Expand to secure secondary nodes and Arcana relics.
3. Invest in tech → unlock advanced units to handle zombie phases.

## 6. Tech Progression
**Base Tech Tree (shared across all nations)**
- **Tier 1:** Basic infantry, workers, scouting.
- **Tier 2:** Mid-game power spike, defensive tech, first wave counters.
- **Tier 3:** Elite units, siege, and zombie phase responses.
- **Tier 4 (Legacy Tech):** Faction-specific path with high-impact upgrades.

**Research Examples**
- Fortified walls, improved armor plating, ranged weapon calibration.
- Anti-horde tools (splash damage, slow fields, suppression towers).
- Zombie resilience counters (disease resistance, cleansing tech).

## 7. Units & Roles
**Unit Archetypes**
- Workers, infantry, skirmishers, siege, casters, elite units.

**Special Systems**
- **Morale:** Units gain morale by fighting zombies, temporarily boosting stats.
- **Supply Lines:** Remote bases require supply depots; cut supply reduces efficiency.

## 8. Zombie AI & Phases
Zombies are controlled by AI with adaptive strategies based on player expansion.

**Phase 1 — Scouting Swarm (0–15 min)**
- Small hordes test defenses; basic zombie types.

**Phase 2 — Corruption Spread (15–30 min)**
- New zombie types: burrowers, spitters, plague carriers.
- Corruption zones reduce player resource yield.

**Phase 3 — Siege of the Living (30–45 min)**
- Massive waves; siege zombies target structures.
- Zombie nests grow and spawn minibosses.

**Phase 4 — The Dark Tide (45+ min)**
- Boss-level undead leaders.
- Global debuffs and periodic mega-waves.
- Triggers final evacuation objective if enabled.

## 9. Map & Objectives
- **Primary Map:** Large continent with 8 starting regions.
- **Secondary Zones:** 2–3 neutral zones for Arcana relics and bonuses.
- **Zombie Nests:** Occupied areas that must be weakened to reduce waves.

**Optional Objective: Evacuation Beacon**
- Build the beacon after Phase 4 starts.
- Requires joint defense and resource contributions.

## 10. Multiplayer & UX
- **Lobby:** Nation selection, difficulty modifiers, zombie AI toggles.
- **Co-op Tools:** Pings, shared map vision, and temporary alliances.
- **Spectator Mode:** Fog-of-war controls, zombie POV toggle.

## 11. Technical Scope (Engine-Agnostic)
- **Networking:** Client-server authority with lockstep simulation.
- **AI:** Behavior trees + threat evaluation per player base.
- **Modularity:** JSON/Scriptable data for units, tech, and zombies.

## 12. Art & Audio Direction
- **Visuals:** Gritty fantasy + steampunk elements.
- **Color:** Clear faction palettes; undead = sickly greens/purples.
- **Audio:** Distinct faction motifs, escalating zombie soundscape.

## 13. Milestones
1. **Prototype (4–6 weeks)**
   - Basic RTS loop, worker economy, zombie wave AI.
2. **Vertical Slice (8–12 weeks)**
   - 3 nations, full tech tiers, multiplayer for 4 players.
3. **Alpha (12–20 weeks)**
   - All 8 nations, complete zombie phases.
4. **Beta (20–28 weeks)**
   - Balance pass, performance tuning, UX polish.

## 14. Risks & Mitigations
- **Balance Complexity:** Use data-driven tuning + telemetry.
- **Zombie AI Scaling:** Cap wave sizes dynamically.
- **Multiplayer Desync:** Deterministic lockstep simulation.

## 15. Success Metrics
- 30–40% of matches reach Phase 4.
- High player engagement with cooperative objectives.
- Clear differentiation between nation playstyles.
