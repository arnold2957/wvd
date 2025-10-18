# wvdas - Wizardry Daphne Auto Script
An auto-farming script for the mobile game Wizardry Daphne with a built-in GUI.

Compared to other popular game automation scripts, it includes special optimizations specifically for the ***complex network environment*** and ***occasional performance fluctuations*** of Wizardry Daphne.

## What features does wvdas have that ordinary scripts cannot do?
### Auto Restart
Game crashed? Restarts instantly!

Network issue? Instantly clicks "Retry". Stuck on loading? Restarts the game!

Stuck in a chest, stuck in a door, stuck in battle, stuck in the chest-opening process—wvdas can detect "static screens" or "excessively long durations" and automatically restart the game.

### "Zero-Fire Switch to Money Begging"
Woke up to find the "Flame of Reawakening" depleted, and the game stuck at the Cursed Wheel, wasting time?

wvdas can detect when the "Flame of Reawakening" is depleted and immediately change the objective to "Begging Money from Princess".

Maximizes AFK efficiency~

## How to install the emulator and set up the script?
### Emulator Setup
*BlueStacks is no longer maintained. Please do not use BlueStacks emulator anymore.*
- Download MuMu emulator, either MuMu12 or MuMuX is fine.
- Install the game APK.
- If you encounter a black screen on first load, please install the Google Play Services. You can install them directly from the MuMu desktop.
- If you encounter a Google login popup, press the back button repeatedly.
- If you encounter "Violation of Security Policy", disable root.
- If you encounter "unable to initialize the unity engine graphics API", switch to DirectX first, then use Vulkan to start the game normally.
- The emulator has **ADB debugging enabled**.
- Emulator resolution is **1600x900**, 240 DPI.

### Emulator Settings
- The "Emulator Path" in the top-left corner of the script is:
     - MuMu12: Netease\MuMu Player 12\shell\MuMuPlayer.exe
     - MuMuX: Netease\MuMu\nx_device\12.0\shell\MuMuNxDevice.exe
- The port number is 5555 or 16384. If neither works, you can find the ADB port number in the Multi-Drive Manager.

### Overall Game Settings
- The game is set to the **English version**.
- Graphics quality is set to **Medium (Prioritize Speed)**.
- Set Frame Rate to **30 FPS**, and Dungeon Brightness to **Darkest -25% Brightness**.
- In the Auto-Recovery settings, check "Use skills to dispel abnormal statuses".
- In the Inventory Refill settings, check "Place all non-refill items in storage" and "Automatically refill when staying at the inn.". (If unsure, check "Carry 1 Hook of Harken").
- The game map is **not zoomed in/out**. If zoomed, it is recommended to reinstall the game. (An unzoomed game map should show about 17 grid squares.)
- Skills planned for use **must be placed on the quick slot bar**, but **cannot be placed in the top-left** quick slot.
- **Disable automatic branch selection in dialogues**. Currently, the Princess money begging and Horned Eagle scripts are designed assuming automatic branch selection is off.

### In-Dungeon Settings
- The game map must be **fully explored**. For maps that use target point detection, at least the entire target area must be explored.
- It's best to have unlocked the Great Harken for the target map.
- After checking "Cast AoE only once per battle", enabled LA-series spells and Secret Arts will only be cast once per battle. You still need to manually enable Secret Arts or AoE spells.
- After checking "Switch to Auto-battle after AoE", the script will switch to auto-battle after casting the AoE. You still need to manually enable Secret Arts or AoE spells.
- If SP is insufficient, it will automatically switch to using Lv.1 skills. However, subsequent battles will continue using Lv.1 skills. To avoid this, adjust the inn rest frequency.
- If characters get stuck and cannot move upon entering the dungeon, this is caused by network issues; try changing your accelerator.

### Headless Mode
You can launch Wvd in Headless mode!

Create a shortcut for wvd.exe and add " -headless" to the end of the "Target" field.

You can also use "-config path" to specify a particular configuration file.

### Script Settings
- "Smart Chest-opening" is based on image recognition and fitting a triangular wave for prediction.
    - Currently, it uses 20 screenshots for prediction, which is quite time-consuming. *(Will be fixed in a future version!)*
- "Chest Opener: Random" will randomly assign a character.
- If a fixed chest opener is specified, it will switch to another random character if the assigned one is Feared or Petrified.
- "Inn Rest Interval" is the number of dungeon runs between rests. 0 means rest every time, 1 means rest every other run, and so on. After disabling "Enable Inn Rest", resting at the inn will be permanently skipped for farming dungeons and some quest dungeons.
- "Post-battle Recovery" and "Post-chest-opening Recovery" refer to the auto-recovery actions performed after these events. If recovery doesn't dispel abnormal statuses, check the game settings, character skills, and character statuses.

#### Scorpionesses Bounty
- Level 7 Bounty Scorpionesses are the optimal balance of difficulty and efficiency. Since the difficulty before level 7 is not high, earlier bounties are not currently considered.
- Ninjas can one-shot Scorpionesses, so try forming a team with 3 or more Ninjas.
- The frontline needs about 180 Evasion to almost never get hit, and the backline won't get targeted consecutively, so just enable "Use Class Skills" for the Priest to AFK.
- Reference Team - Do not cast attack skills:
  - Frontline: Stack 180 Evasion, Priest, and any character (recommend Ninja). No Attack, Divine Power, or other requirements.
  - Backline: Normal Attack-stacked Spear/Bow Warriors, or Attack-stacked Kunai Ninjas.

#### Dark Light in the Death God
- This quest aims to farm Dark Resistance equipment and Alt character EXP.
- As the monsters hit hard, ensure everyone has a Light-element weapon (or several Pioneer Slashes) before attempting.
- Interact with the door in the upper left corner of the Death God map to accept the quest, then clear all wandering monsters around one Dark Light.
- Face the Dark Light and start the script.

#### Fortress 7F Giant Farming
- Start from the Fortress and kill the Giant at the entrance of 7F.
- First, you need to repeatedly reset the 7F map (by jumping to Chapter 1, then Chapter 2, and jumping back) until the 7F map becomes the **special map**:
    - When standing behind the Giant, you should be able to see [a lamp](resources/images/gaint_candelabra_1.png).
- Because the Giant is tough and the battle is complex, this quest features a **custom skill sequence function**. Meanwhile, the entire original skill configuration panel is completely ineffective for this quest.
- **Due to skill name changes, the custom skill sequence is temporarily unavailable.**
~~- The default skill sequence is for the following low-investment team:
    - Two-person team, Samurai and Mask MC Mage. Samurai in front row, Mask Mage behind the Samurai.
    - Samurai casts skills in this order: Defend, Quickdraw x N.
    - Mask Mage casts skills in this order: LACONES x3, Defend x N.
- You can customize your team's skill sequence by accessing `wvd\_internal\resources\quest\quest.json`. Find the `'gaintKiller'` - `'_SPELLSEQUENCE'` entry.
- You can delete `'_SPELLSEQUENCE'` and the content after the colon to completely skip the custom skill sequence.
- You can also customize it. Each line under `'_SPELLSEQUENCE'` follows these rules:
    - `"Character who has this skill in their bar":["Cast this first","then this","finally spam this"]`
    - For example, in the default setup, the Mask Mage casts: LACONES x3, Defend x N.
        - So, we write `"LACONES":["LACONES","LACONES","LACONES","defend"],`
    - Note: The skill used for identification and the skills in the sequence don't necessarily have to match. You can write something like "Character carrying DTS casts Quickdraw twice then Defend"
        - So, you could write `"DTS":["QS","QS","defend"],`
    - Skill names are the "full name for spells" and "first letters for physical skills".
- A freely configurable panel will be implemented in the future.~~

#### Cave of Separation / Sword of Promises:
- The chest-opening difficulty in this cave is high. Recommended Thief MC or a specially trained chest-opening tool character.
- Clarissa can significantly simplify the battles in this cave. By placing her in the center front row, you can effectively resist the Succubus's Charm. You can use full Auto-battle.
- Otherwise, recommend a quickest AOE Damage Dealer (Speed > 90, Magic Power > 450) to one-shot the Succubi, plus Alice in the backrow and a frontline Aura Source to supplement 20% damage.
- This cave has many battles. Recommend bringing 2 sets of AoE + Damage-Boost combinations. Alternatively, bring 1 set and 2 Alt characters.
- Reference AoE + Damage-Boost combinations:
      Sheliri + Milana (Excellent sustainability, can pick locks) > Yeka + Elisa (Prevents ambushes, one Aura is enough, but poor sustainability) > Adam + Debra (Can pick locks, but poor sustainability) > Adam + Abe (Pioneer Slash wastes time and deals ineffective damage, poor sustainability, not recommended)

#### Three Gorgons:
- Start from Time Jump, target point is "Defeat Our Glory". Ensure you kill the Doll. Note: The first time jumping to the Doll might not unlock the Harken, requiring manual operation.
- Basic流程: Jump -> Upper left Gorgon -> **Return to Inn (Optional)** -> Right two Gorgons -> Jump. To disable the return to inn during the process, disable "**Enable Inn Rest**".
- Low-investment team recommendation: 4-character team.
    - 2 Warriors, 160+ Evasion, 300+ Attack, +20 ebronsteel weapons (or Horned Eagle Sword), only use Full Power Attack.
    - 1 Priest, slowest speed, stack Evasion as high as possible, **stand in front row**, only cast KANTIOS.
    - 1 Mage / 1 Priest, fastest speed, stack Magic Power as high as possible, **stand behind the Priest**, cast LA-series spells or Secret Arts.
    - Skill Enable: Disable system Auto-battle, check "Crowd Control", "Powerful Single-target", and "AOE".
    - Recommended to check 'Skip **Post-chest-opening** Recovery', "Enable Inn Rest".
    - The threat of the Gorgons lies in their ability to swap front/back row positions and Petrifying Breath. High Evasion Priest counters position swaps, and a formation with only front row characters also counters swaps. As for Petrifying Breath, the high-Evasion Priest can handle it.
    - Reference Team: Warrior Mask upper left, Priest Yeka upper center, Warrior Princess upper right, Sleep Mage lower center.
    - Variant Team: Priest Mask upper left, Warrior Elisa upper center, Warrior Princess upper right, Priest Yeka lower center.
        - Use Priest Yeka's Secret Arts as the Mage's AoE. With Elisa's Aura, damage is sufficient.
        - Elisa stands in front of Yeka, needs Evasion. But due to double Aura, damage is sufficient.
#### Sand Shadow Cave:
- The inn for this quest is the Fortress. Ensure the Fortress is visible.
- Not recommended to use the script without completing the 2nd playthrough.
- Note: This quest requires **completing the 2nd playthrough and obtaining the Disarm Trap knowledge**. Obtain the knowledge from the boss room after the 2nd playthrough to learn how to disable traps.
- Note: **The hidden areas in the lower left and right corners of the 1F map are very easy to miss**. Check Gamerch to confirm the map is fully explored: [Guide](https://gamerch.com/wizardry-daphne/928695), and [Map](https://cdn.gamerch.com/resize/eyJidWNrZXQiOiJnYW1lcmNoLWltZy1jb250ZW50cyIsImtleSI6Indpa2lcLzQ3MTRcL2VudHJ5XC9DVGJLWWRESy5qcGciLCJlZGl0cyI6eyJ0b0Zvcm1hdCI6IndlYnAiLCJqcGVnIjp7InF1YWxpdHkiOjg1fX19)
- Currently, three versions are provided:
    - 1F Backtrack Gold Chest Farming. Process: Backtrack -> Two Ninjas -> Three Gold Chests -> Other Chests.
    - Monster Farming. A route that passes through 7 monsters, triggering about 5 battles per run on average.
    - Loot All. Based on Monster Farming, additionally searches for chests on the map.
#### Trade Waterway - Shiphold 2nd Floor:
- Ensure the entire upper half of Ship 1 map is lit, and the entire upper half of Ship 2 map is lit.
#### Ore Den:
- The Earth Den currently has only one target point. Defeat it and return to town.
- Ensure the entire first large square area of the Fire Den is lit, especially the lower left part of the large square.
- Ensure the entire first large square area of the Light Den is lit, especially the central area of the large square.

~~#### "Repel the Enemy Force" Quest:
- Does not include Time Jump, map exploration, or the quest acceptance part.
- The Inn Rest Interval controls how many times the "defeat the first 2 waves" operation is repeated before returning to town within one Ship Bridge run. For example, if Rest Interval = 2, then 2 rounds are repeated, totaling 2x2=4 battles and 4 AoE casts.
- Ensure the entire 7th District map is lit.
- Try to ensure the Mage is the fastest and can wipe all monsters in one AoE cast, otherwise the script has a low risk of getting stuck.~~

#### "Horned Eagle Sword" Quest:
- The panel **only controls the final boss fight**; the mobs on the way are **forced Auto-battle**. The process does not include returning to town, so attempt according to your strength.
- Ensure certain areas of certain maps are fully explored.
- Activating the Harken on the third layer has a chance to fail and cause character death. *(Temporarily won't be fixed!)*

## How to report information?
- Send log.txt.
- Send the screenshots from the screenshotwhenrestart folder next to the exe.
- Send screenshots of the in-game map and screen.

## I have an idea / I want to contribute code
Thank you for your interest in supporting this project! But first, please visit the wiki for more information.
