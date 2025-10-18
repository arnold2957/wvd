# wvdas - Wizardry Daphne Auto Script
An auto-farming script for the mobile game Wizardry Daphne with a built-in GUI.

Compared to other popular game automation scripts, it includes special optimizations for the ***complex network environment*** and ***occasional performance fluctuations*** specific to Wizardry Daphne.

## What features does wvdas have that ordinary scripts lack?
### Auto Restart
Game crashed? Restarts immediately!

Network issue? Instantly clicks "Retry". Stuck on a loading screen? Restarts the game!

Stuck in a chest, stuck in a door, stuck in battle, stuck in the chest-opening sequence - wvdas can detect a "frozen screen" or "excessively long operation time" and automatically restart the game.

### "Zero-Fire Switch to Money Begging"
Woke up to find the "Flame of Reawakening" depleted, the game stuck at the Cursed Wheel, wasting precious time?

wvdas can detect when the "Flame of Reawakening" is depleted and immediately change the objective to "Begging Money from the Princess".

Maximizes AFK efficiency~

## How to install the emulator and set up the script?
### Emulator Setup
*BlueStacks is no longer maintained. Please stop using BlueStacks.*
- Download the MuMu emulator, either MuMu12 or MuMuX is fine.
- Install the game APK.
- If you encounter a black screen on first load, please install the Google Mobile Services. They are available directly on the MuMu desktop.
- If you encounter a Google login popup, press the Back button repeatedly until it closes.
- If you encounter "Violation of Security Policy", disable root access.
- If you encounter "unable to initialize the unity engine graphics API", first switch to start with DirectX, then switch to Vulkan to start the game normally.
- The emulator must have **ADB debugging enabled**.
- Set the emulator resolution to **1600x900**, 240 DPI.

### Emulator Paths
- The "Emulator Path" in the top-left corner of the script should be:
     - MuMu12: `Netease\MuMu Player 12\shell\MuMuPlayer.exe`
     - MuMuX: `Netease\MuMu\nx_device\12.0\shell\MuMuNxDevice.exe`
- The port number is 5555 or 16384. If neither works, you can find the ADB port number in the Multi-Drive Manager.

### General Game Settings
- The game must be set to the **English** language.
- Set Graphics Quality to **Medium (Prioritize Speed)**.
- Set Frame Rate to **30 FPS**, and Dungeon Brightness to **Darkest -25% Brightness**.
- In the Auto-Recovery settings, check "Use Skills to Remove Status Ailments".
- In the Bag Refill settings, check "Place all non-refill items in storage" and "Automatically refill when staying at the inn." (If 'Refill' Buttom is disable, also check "Carry 1 Hook of Harken").
- The game map must be **unzoomed**. If you have already zoomed the map, it is recommended to reinstall the game. (An unzoomed game map should show about 17 grid squares.)
- Skills planned for use **must be placed on the quick slot bar**, but **must NOT be placed in the top-left** quick slot.
- **Disable automatic branch selection in dialogues**. The current Princess money begging and Horned Eagle quest implementations are based on this setting being off.

### In-Dungeon Settings
- The dungeon map must be **fully revealed**. For maps that use target point detection, at least the entire target area must be revealed.
- It is best to have the Great Harken for the target dungeon already unlocked in the game.
- Checking "Cast Full-party AOE only once per battle" will cause enabled LA-series spells and Secret Arts to be cast only once per battle. You still need to manually enable the Secret Art or AOE skill.
- Checking "Enable Auto-battle after Full-party AOE" will switch to auto-battle after casting the AOE. You still need to manually enable the Secret Art or AOE skill.
- If SP runs low, it will automatically switch to using the Lv1 version of the skill. However, subsequent battles will continue using the Lv1 skill. To avoid this, adjust the Inn Rest interval.
- If characters get stuck and cannot move immediately upon entering a dungeon, this is caused by network issues. Please try a different game accelerator.

### Headless Mode
You can launch Wvd in Headless Mode!

Create a shortcut for `wvd.exe` and add ` -headless` to the end of the "Target" field in the shortcut properties.

You can also use `-config path` to specify a particular configuration file.

### Script Settings
- "Smart Chest-opening" is based on image recognition and fitting a triangular wave for prediction.
    - It currently uses 20 screenshots for prediction, which is quite time-consuming. *(Will be fixed in a future version!)*
- "Chest Opener: Random" will randomly assign a character.
- If a fixed chest opener is specified, it will switch to another random character if the specified one is Feared or Petrified.
- "Inn Rest Interval" is the number of dungeon runs *between* each rest. 0 means rest after every run, 1 means rest every other run, and so on. Disabling "Enable Inn Rest" will permanently skip Inn Rests during farming dungeons and some quest dungeons.
- "Post-battle Recovery" and "Post-chest-opening Recovery" refer to the auto-recovery actions performed after these events. If recovery isn't removing status ailments, check your game settings, character skills, and the character's status ailments.

#### Scorpionesses Bounty
- The Level 7 Scorpionesses Bounty is the optimal balance of difficulty and efficiency. Since the difficulty before level 7 isn't high, lower level bounties are not currently considered.
- Ninjas can instantly kill Scorpionesses, so try forming a party with 3 or more Ninjas.
- With 180 Evasion in the front row, they will almost never get hit, and the back row won't get targeted consecutively. Therefore, simply having a Priest with "Use Class Skills" enabled is sufficient for AFK.
- Sample Budget Team - No attack skills enabled:
    - Front Row: A Priest with 180+ Evasion and any other character (recommend Ninja). No specific Attack or Divine Power requirements.
    - Back Row: Normal Lance/Bow Warriors or Kunai Ninjas built for Attack.

#### Dark Light in the Death God
- This quest aims to farm Dark Resistance equipment and EXP for alternate characters.
- Due to high monster attack, ensure everyone is equipped with a Light-element weapon (or a few Pioneer Slashes) before attempting.
- Interact with the object in the upper-left corner of the Death God map to accept the quest, then clear all wandering monsters around one Dark Light.
- Face the Dark Light and then start the script.

#### Fortress 7F Giant Farming
- Start from the Fortress, kill the single Giant at the entrance of 7F.
- First, you need to repeatedly reset the 7F map (by jumping to Chapter 1/Chapter 2 and then jumping back) until the 7F map becomes the **specific map layout**:
    - When standing behind the Giant, you should be able to see [a specific candelabra](resources/images/gaint_candelabra_1.png).
- Because the Giant is tough and the battle is complex, this quest features a **custom skill sequence function**. The standard skill configuration panel is completely inactive for this quest.
- The default skill sequence is designed for the following low-investment team:
    - Two-character party: Samurai and Masked Mage (MC). Samurai in front, Masked Mage directly behind.
    - Samurai skill sequence: Defend, then Quickdraw x N.
    - Masked Mage skill sequence: LACONES x 3, then Defend x N.
- You can customize your party's skill sequence by accessing `wvd\_internal\resources\quest\quest.json`. Find the `'gaintKiller'` -> `'_SPELLSEQUENCE'` entry.
- You can delete the `'_SPELLSEQUENCE'` key and its subsequent content to completely skip the custom skill sequence.
- You can also customize it. Each line under `'_SPELLSEQUENCE'` follows this rule:
    - `"Character who has this skill on their bar":["First cast this","Then cast this","Finally spam this"]`
    - For example, in the default setup, the Masked Mage casts: LACONES x 3, then Defend x N.
        - So, we write: `"LACONES":["LACONES","LACONES","LACONES","defend"],`
    - Note: The skill used for identification and the skills in the sequence don't necessarily have to match. You could write something like "The character carrying DTS casts Quickdraw twice then defends"
        - So, you could write: `"DTS":["QS","QS","defend"],`
    - Skill names are the "full name for spells" and the "first letters for physical skills" (as per the terminology list).
- A freely configurable panel for this will be implemented in the future.

#### Cave of Separation / Sword of Promises:
- The chests in this cave are difficult to open. Recommended to use a Masked MC or a specially trained chest-opening character.
- This cave contains high-speed Succubi. Recommended to have a quickest AOE Damage Dealer to kill them, requiring Speed > 90, Magic Power > 450, plus Alice in the back row and an Aura Source in the front row to provide a 20% damage boost.
- Consecutive runs involve many battles. Recommended to bring 2 sets of AOE + Aura Source pairs. Alternatively, bring 1 set plus 2 alternate characters.
- Sample AOE + Aura Source pairs:
      Sheliri + Milana (Good sustainability, can pick locks) > Yeka + Elisa (Prevents ambushes, one aura is enough, but poor sustainability) > Adam + Debra (Can pick locks, poor sustainability) > Adam + Abe (Pioneer Slash wastes time with overkill, poor sustainability, not recommended)

| Masked MC | Aura Source / Damage-Boost Provider | Second Aura Source or Alt |
| --- | --- | --- |
| Alice | quickest AOE Damage Dealer | Second AOE Damage Dealer or Alt |

#### Three Gorgons:
- Start from Time Jump, set the destination to "Defeat Our Glory". Ensure you have killed the Doll. Note: The first time jumping to the Doll might not unlock the Harken point, requiring manual operation.
- Basic flow: Jump -> Top-left Gorgon -> **Return to Inn Rest (Optional)** -> Two Gorgons on the right -> Jump. To disable the intermediate Inn Rest, disable "**Enable Inn Rest**".
- Low-investment Team Recommendation: 4-character party.
    - 2 Warriors, 160+ Evasion, 300+ Attack, +20 ebonsteel weapons (or Horned Eagle Sword), only use Full Power Attack.
    - 1 Priest, slowest speed, stack Evasion as high as possible, **place in front row**, only use KANTIOS.
    - 1 Mage / 1 Priest, fastest speed, stack Magic Power as high as possible, **place directly behind the Priest**, use LA-series spells or Secret Arts.
    - Skill Enablement: Disable system Auto-battle, check "Crowd Control (CC)", "Powerful Single-target", and "AOE".
    - Recommended to check 'Skip **Post-chest-opening** Recovery', "Enable Inn Rest".
    - Sample Team: Warrior Masked MC top-left, Priest Yeka middle-top, Warrior Princess top-right, Sheliri (Sleep Mage) middle-bottom.
    - Variant Team: Priest Masked MC top-left, Warrior Elisa middle-top, Warrior Princess top-right, Priest Yeka middle-bottom.
        - Uses Priest Yeka's Secret Art as the AOE. With Elisa's aura, damage is sufficient.
        - Elisa stands in front of Yeka, needs Evasion. Damage is sufficient due to double auras.

#### Sand Shadow Cave:
- The Inn for this quest is the Fortress. Ensure the Fortress is visible.
- Not recommended to use the script without completing the 2nd playthrough (NG+).
- Note: This quest requires **completing the 2nd playthrough and obtaining the Disarm Traps knowledge**. Obtain the knowledge from the boss room after finishing NG+ to understand how to disable the traps.
- Note: **The hidden areas in the bottom-left and bottom-right corners of the 1F map are very easy to miss**. Check Gamerch to confirm the map is fully revealed: [Guide](https://gamerch.com/wizardry-daphne/928695), and [Map](https://cdn.gamerch.com/resize/eyJidWNrZXQiOiJnYW1lcmNoLWltZy1jb250ZW50cyIsImtleSI6Indpa2lcLzQ3MTRcL2VudHJ5XC9DVGJLWWRESy5qcGciLCJlZGl0cyI6eyJ0b0Zvcm1hdCI6IndlYnAiLCJqcGVnIjp7InF1YWxpdHkiOjg1fX19)
- Currently, two versions are provided:
    - 1F Backtracking Gold Chest Run. Flow: Backtrack -> Two Ninjas -> Three Gold Chests -> Other Chests.
    - Monster Farming. A route that passes through 7 monsters, triggering about 5 battles per run on average.

#### Trade Waterway - Shiphold 2nd Floor:
- Ensure the entire upper half of Ship 1 map is revealed, and the entire upper half of Ship 2 map is revealed.

#### Ore Den:
- The Earth Den currently has only one target point. It will return to town after completing it.
- Ensure the entire first large square area of the Fire Den is revealed. Especially the bottom-left part of the large square.
- Ensure the entire first large square area of the Light Den is revealed. Especially the central area of the large square.

~~#### "Repel the Enemy Force" Quest:
- Does not include Time Jump, map exploration, or quest acceptance parts.
- The Inn Rest Interval controls how many times the "defeat the first 2 waves" operation is repeated within one Pier run before returning to town. For example, if Rest Interval = 2, it will repeat 2 cycles, totaling 2x2=4 battles and 4 AOE casts.
- Ensure the entire 7th District map is revealed.
- Try to ensure the Mage is the fastest and can wipe all monsters in one AOE cast, otherwise the script has a low risk of getting stuck.~~

#### "Horned Eagle Sword" Quest:
- The panel **only controls the final boss fight**. Battles against regular enemies on the way are **forced Auto-battle**. The process does not include returning to town, so attempt according to your party's strength.
- Ensure certain specific areas in certain maps are fully revealed.
- Activating the Harken on the third layer has a chance to fail and cause a character death. *(Temporarily no plan to fix!)*

## How to report issues or provide feedback?
- Send the `log.txt` file.
- Send the screenshots from the `screenshotwhenrestart` folder located next to the executable.
- Send screenshots of the in-game map and screen.

## I have an idea / I want to contribute code
Thank you for your interest in supporting this project! Please visit the wiki first to learn more.
