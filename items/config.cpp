// TLB CARP - the CARP Computer.
//
// The drop computer's own config (addon/config.bin) is pre-binarized and cannot be
// rebuilt, so the item lives in this second addon, as plain text. The engine reads an
// unbinarized config.cpp inside a PBO without complaint, and keeping it as text means
// the build needs no Bohemia tooling.
//
// Carrying a TLB_CARP_Computer is what fn_canUseCarp checks before offering TLB CARP
// in an aircraft's interaction menu, and before sharing the crew's CARP record with a
// player. A mission that does not hand the item out can switch the requirement off
// with the "Require CARP Computer" addon option.

class CfgPatches {
    class tlb_carp_items {
        name = "TLB CARP - CARP Computer";
        author = "TLB";
        url = "";
        units[] = {"TLB_CARP_Item_Computer"};
        weapons[] = {"TLB_CARP_Computer"};
        requiredVersion = 2.14;
        requiredAddons[] = {"cba_common"};
    };
};

class CfgWeapons {
    class CBA_MiscItem;
    class CBA_MiscItem_ItemInfo;

    class TLB_CARP_Computer: CBA_MiscItem {
        scope = 2;
        scopeArsenal = 2;
        scopeCurator = 2;
        author = "TLB";
        displayName = "CARP Computer";
        descriptionShort = "Rugged aircrew drop computer. Carry it to open TLB CARP from an aircraft's interaction menu and to share the crew's drop solution.";
        picture = "\x\tlbcarp\addons\items\data\tlb_carp_computer_ca.paa";
        model = "\a3\props_f_exp_a\Military\Equipment\Tablet_02_F.p3d";

        class ItemInfo: CBA_MiscItem_ItemInfo {
            mass = 30;
        };
    };
};

// So Zeus and the editor can put one on the ground.
class CfgVehicles {
    class Item_Base_F;

    class TLB_CARP_Item_Computer: Item_Base_F {
        scope = 2;
        scopeCurator = 2;
        author = "TLB";
        displayName = "CARP Computer";
        vehicleClass = "Items";
        editorCategory = "EdCat_Equipment";
        editorSubcategory = "EdSubcat_InventoryItems";

        class TransportItems {
            class TLB_CARP_Computer {
                name = "TLB_CARP_Computer";
                count = 1;
            };
        };
    };
};
