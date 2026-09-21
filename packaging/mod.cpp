// Canonical mod.cpp template for the release ZIP (not part of the PBO).
// build_release.py replaces the version placeholder on the name line below, so
// the Arma launcher entry states which build is loaded.
// Keep the number in sync with USAFDC_VERSION in addon/functions/fn_postInit.sqf
// -- build_release.py fails the build if the two disagree.
name = "TLB CARP System (Computed Air Release Point) v{VERSION}";
author = "TLB MilSim";
// The logo ships in TLB_CARP_Items.pbo. That addon is packed straight from items/,
// while the drop computer's PBO only takes a new file through a base-release include.
picture = "\x\tlbcarp\addons\items\data\logo_ca.paa";
logo = "\x\tlbcarp\addons\items\data\logo_ca.paa";
logoSmall = "\x\tlbcarp\addons\items\data\logo_small_ca.paa";
logoOver = "\x\tlbcarp\addons\items\data\logo_ca.paa";
tooltip = "TLB CARP";
tooltipOwned = "TLB CARP";
overview = "A drop computer for cargo aircraft. It works out where to let go so the load lands on the drop zone, from the aircraft's live state, and can fly the run-in for you. Everyone aboard carrying a CARP Computer shares one CARP.";
description = "Dynamic CARP guidance with optional player autopilot, package TOT, release stability, and USAF cargo Auto Drop for C-17/C-130 cargo operations. Requires CBA_A3 and ACE3. Licensed APL-ND.";
actionName = "GitHub";
action = "https://github.com/TLB-MilSim/TLB-CARP-System";
