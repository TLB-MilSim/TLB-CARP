// WARNING: this file is compiled into the pre-binarized config.bin, which cannot
// be regenerated without Bohemia tooling. Editing the geometry below has NO
// in-engine effect. Every HUD control position is set at runtime in
// functions/ui/fn_updateHud.sqf via ctrlSetPosition -- change it there.
class RscTitles {
    class TLB_CARP_HUD {
        idd = -1;
        movingEnable = 0;
        enableSimulation = 1;
        fadeIn = 0;
        fadeOut = 0;
        duration = 1e10;
        onLoad = "uiNamespace setVariable ['TLB_CARP_HUD_display', _this # 0]; uiNamespace setVariable ['TLB_CARP_HUD_STEER', (_this # 0) displayCtrl 9402];";
        onUnload = "uiNamespace setVariable ['TLB_CARP_HUD_display', displayNull]; uiNamespace setVariable ['TLB_CARP_HUD_STEER', controlNull];";

        class controls {
            class Guidance: RscStructuredText {
                idc = 9401;
                x = "safeZoneX + safeZoneW * 0.335";
                y = "safeZoneY + safeZoneH * 0.025";
                w = "safeZoneW * 0.33";
                h = "safeZoneH * 0.20";
                text = "";
                colorBackground[] = {0.02, 0.03, 0.035, 0.68};
            };
            class SteeringCue: RscStructuredText {
                idc = 9402;
                x = "safeZoneX + safeZoneW * 0.4875";
                y = "safeZoneY + safeZoneH * 0.238";
                w = "safeZoneW * 0.025";
                h = "safeZoneH * 0.026";
                text = "<t align='center' size='1.35' color='#66e6a6'>^</t>";
                colorBackground[] = {0,0,0,0};
            };
            class SteeringCenter: RscStructuredText {
                idc = 9403;
                x = "safeZoneX + safeZoneW * 0.4875";
                y = "safeZoneY + safeZoneH * 0.263";
                w = "safeZoneW * 0.025";
                h = "safeZoneH * 0.026";
                text = "<t align='center' size='1.25' color='#ffffff'>|</t>";
                colorBackground[] = {0,0,0,0};
            };
        };
    };
};
