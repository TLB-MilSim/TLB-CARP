class TLB_CARP_RscDialog: RscDisplayEmpty {
    idd = IDD_TLB_CARP_DIALOG;
    movingEnable = 0;
    enableSimulation = 1;
    onLoad = "uiNamespace setVariable ['TLB_CARP_display', _this # 0]; [] spawn {uiSleep 0.01; [] call TLB_CARP_fnc_refreshPanel};";
    onUnload = "uiNamespace setVariable ['TLB_CARP_display', displayNull];";

    class controlsBackground {
        class Background: RscText {
            idc = -1;
            x = "safeZoneX + safeZoneW * 0.30";
            y = "safeZoneY + safeZoneH * 0.15";
            w = "safeZoneW * 0.40";
            h = "safeZoneH * 0.70";
            colorBackground[] = {0.02,0.03,0.035,0.96};
        };
        class Title: RscText {
            idc = -1;
            text = "TLB CARP - COMPUTED AIR RELEASE POINT";
            x = "safeZoneX + safeZoneW * 0.315";
            y = "safeZoneY + safeZoneH * 0.17";
            w = "safeZoneW * 0.37";
            h = "safeZoneH * 0.04";
            sizeEx = 0.038;
            colorText[] = {0.4,0.9,0.65,1};
        };
    };

    class controls {
        class DZLabel: RscText { idc=-1; text="DZ"; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.225"; w = "safeZoneW*0.08"; h = "safeZoneH*0.03"; };
        class DZCombo: RscCombo {
            idc = IDC_TLB_CARP_DZ;
            x = "safeZoneX+safeZoneW*0.40"; y = "safeZoneY+safeZoneH*0.225"; w = "safeZoneW*0.18"; h = "safeZoneH*0.03";
            onLBSelChanged = "if (!TLB_CARP_state_panelRefreshing) then {private _m=(_this#0) lbData (_this#1); if (_m!='') then {private _d=[] call TLB_CARP_fnc_getMissionDZs; private _i=_d findIf {(_x#0) isEqualTo _m}; if (_i>=0) then {[(_d#_i)#2, (_d#_i)#1] call TLB_CARP_fnc_setDZ}; [] call TLB_CARP_fnc_refreshPanel}}";
        };
        class MapDZ: RscButton { idc=IDC_TLB_CARP_MAP_DZ; text="SET DZ ON MAP"; x = "safeZoneX+safeZoneW*0.59"; y = "safeZoneY+safeZoneH*0.225"; w = "safeZoneW*0.095"; h = "safeZoneH*0.03"; action="private _d=findDisplay 9300; if (!isNull _d) then {_d closeDisplay 2}; [] call TLB_CARP_fnc_beginMapDZ"; };
        class ClearDZ: RscButton { idc=IDC_TLB_CARP_CLEAR_DZ; text="CLEAR DZ"; x = "safeZoneX+safeZoneW*0.59"; y = "safeZoneY+safeZoneH*0.26"; w = "safeZoneW*0.095"; h = "safeZoneH*0.03"; action="[] call TLB_CARP_fnc_clearDZ; [] call TLB_CARP_fnc_refreshPanel"; };

        class ModeLabel: RscText { idc=-1; text="MODE"; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.275"; w = "safeZoneW*0.08"; h = "safeZoneH*0.03"; };
        class ModeCombo: RscCombo {
            idc=IDC_TLB_CARP_MODE; x = "safeZoneX+safeZoneW*0.40"; y = "safeZoneY+safeZoneH*0.275"; w = "safeZoneW*0.18"; h = "safeZoneH*0.03";
            onLBSelChanged="if (!TLB_CARP_state_panelRefreshing) then {private _v=(_this#0) lbData (_this#1); if (_v in ['TOUCHDOWN','CHUTE']) then {[] call TLB_CARP_fnc_disarmAutoDrop; TLB_CARP_state_mode=_v; TLB_CARP_state_dropLatched=false}; [] call TLB_CARP_fnc_refreshPanel}";
        };

        class AircraftLabel: RscText { idc=-1; text="AIRCRAFT"; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.315"; w = "safeZoneW*0.08"; h = "safeZoneH*0.03"; };
        class ProfileCombo: RscCombo {
            idc=IDC_TLB_CARP_PROFILE; x = "safeZoneX+safeZoneW*0.40"; y = "safeZoneY+safeZoneH*0.315"; w = "safeZoneW*0.18"; h = "safeZoneH*0.03";
            onLBSelChanged="if (!TLB_CARP_state_panelRefreshing) then {[] call TLB_CARP_fnc_disarmAutoDrop; TLB_CARP_state_profileOverride=(_this#0) lbData (_this#1); TLB_CARP_state_dropLatched=false; [] call TLB_CARP_fnc_refreshPanel}";
        };

        class WindLabel: RscText { idc=-1; text="WIND"; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.36"; w = "safeZoneW*0.08"; h = "safeZoneH*0.03"; };
        class ManualWind: RscCheckBox { idc=IDC_TLB_CARP_MANUAL_WIND; x = "safeZoneX+safeZoneW*0.40"; y = "safeZoneY+safeZoneH*0.36"; w = "safeZoneW*0.02"; h = "safeZoneH*0.03"; onCheckedChanged="if (!TLB_CARP_state_panelRefreshing) then {TLB_CARP_state_manualWind=(_this#1) isEqualTo 1; [] call TLB_CARP_fnc_refreshPanel}"; };
        class WindSpeed: RscEdit { idc=IDC_TLB_CARP_WIND_SPEED; text="0"; x = "safeZoneX+safeZoneW*0.43"; y = "safeZoneY+safeZoneH*0.36"; w = "safeZoneW*0.06"; h = "safeZoneH*0.03"; tooltip="Wind speed m/s"; };
        class WindFrom: RscEdit { idc=IDC_TLB_CARP_WIND_FROM; text="0"; x = "safeZoneX+safeZoneW*0.50"; y = "safeZoneY+safeZoneH*0.36"; w = "safeZoneW*0.06"; h = "safeZoneH*0.03"; tooltip="Wind FROM degrees"; };
        class ApplyWind: RscButton { idc=IDC_TLB_CARP_APPLY_WIND; text="APPLY WIND"; x = "safeZoneX+safeZoneW*0.57"; y = "safeZoneY+safeZoneH*0.36"; w = "safeZoneW*0.115"; h = "safeZoneH*0.03"; action="TLB_CARP_state_manualWindMs=0 max parseNumber ctrlText ((findDisplay 9300) displayCtrl 9306); TLB_CARP_state_manualWindFromDeg=(parseNumber ctrlText ((findDisplay 9300) displayCtrl 9307)) mod 360; [] call TLB_CARP_fnc_refreshPanel"; };

        class TargetAglLabel: RscText { idc=-1; text="TARGET AGL"; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.397"; w = "safeZoneW*0.08"; h = "safeZoneH*0.03"; };
        class TargetAgl: RscEdit { idc=IDC_TLB_CARP_TARGET_AGL; text="3000"; x = "safeZoneX+safeZoneW*0.40"; y = "safeZoneY+safeZoneH*0.397"; w = "safeZoneW*0.06"; h = "safeZoneH*0.03"; tooltip="Planned drop altitude AGL in meters"; };
        class TargetGsLabel: RscText { idc=-1; text="TARGET GS"; x = "safeZoneX+safeZoneW*0.47"; y = "safeZoneY+safeZoneH*0.397"; w = "safeZoneW*0.075"; h = "safeZoneH*0.03"; };
        class TargetGs: RscEdit { idc=IDC_TLB_CARP_TARGET_GS; text="500"; x = "safeZoneX+safeZoneW*0.545"; y = "safeZoneY+safeZoneH*0.397"; w = "safeZoneW*0.055"; h = "safeZoneH*0.03"; tooltip="Planned ground speed in km/h"; };
        class ApplyProfile: RscButton { idc=IDC_TLB_CARP_APPLY_PROFILE; text="APPLY"; x = "safeZoneX+safeZoneW*0.61"; y = "safeZoneY+safeZoneH*0.397"; w = "safeZoneW*0.075"; h = "safeZoneH*0.03"; action="TLB_CARP_state_targetAglM=(parseNumber ctrlText ((findDisplay 9300) displayCtrl 9320)) max 300; TLB_CARP_state_targetGroundSpeedKmh=(parseNumber ctrlText ((findDisplay 9300) displayCtrl 9321)) max 100; [] call TLB_CARP_fnc_refreshPanel"; };

        class RunIn: RscButton { idc=IDC_TLB_CARP_RUNIN; text="RUN-IN"; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.435"; w = "safeZoneW*0.115"; h = "safeZoneH*0.035"; action="if (TLB_CARP_state_runInLocked) then {[] call TLB_CARP_fnc_unlockRunIn} else {[] call TLB_CARP_fnc_lockRunIn}; [] call TLB_CARP_fnc_refreshPanel"; };
        class Guidance: RscButton { idc=IDC_TLB_CARP_GUIDANCE; text="GUIDANCE"; x = "safeZoneX+safeZoneW*0.44"; y = "safeZoneY+safeZoneH*0.435"; w = "safeZoneW*0.115"; h = "safeZoneH*0.035"; action="if (TLB_CARP_state_guidanceArmed) then {[] call TLB_CARP_fnc_disarmGuidance} else {[] call TLB_CARP_fnc_armGuidance}; [] call TLB_CARP_fnc_refreshPanel"; };
        class AutoDrop: RscButton { idc=IDC_TLB_CARP_AUTO; text="AUTO DROP"; x = "safeZoneX+safeZoneW*0.565"; y = "safeZoneY+safeZoneH*0.435"; w = "safeZoneW*0.12"; h = "safeZoneH*0.035"; action="if !(isNil 'TLB_CARP_fnc_armAutoDrop') then {if (TLB_CARP_state_autoArmed) then {[] call TLB_CARP_fnc_disarmAutoDrop} else {[] call TLB_CARP_fnc_armAutoDrop}}; [] call TLB_CARP_fnc_refreshPanel"; };

        class CargoLabel: RscText { idc=-1; text="CARGO"; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.485"; w = "safeZoneW*0.08"; h = "safeZoneH*0.03"; };
        class CargoCombo: RscCombo { idc=IDC_TLB_CARP_CARGO; x = "safeZoneX+safeZoneW*0.40"; y = "safeZoneY+safeZoneH*0.485"; w = "safeZoneW*0.10"; h = "safeZoneH*0.03"; onLBSelChanged="if (!TLB_CARP_state_panelRefreshing) then {[] call TLB_CARP_fnc_disarmAutoDrop; TLB_CARP_state_cargoCount=parseNumber ((_this#0) lbData (_this#1)); TLB_CARP_state_dropLatched=false; [] call TLB_CARP_fnc_refreshPanel}"; };
        class Debug: RscButton { idc=IDC_TLB_CARP_DEBUG; text="DEBUG"; x = "safeZoneX+safeZoneW*0.51"; y = "safeZoneY+safeZoneH*0.485"; w = "safeZoneW*0.085"; h = "safeZoneH*0.03"; action="TLB_CARP_setting_debug=!TLB_CARP_setting_debug; [] call TLB_CARP_fnc_refreshPanel"; };
        class SelfTest: RscButton { idc=IDC_TLB_CARP_SELFTEST; text="SOLVER TEST"; x = "safeZoneX+safeZoneW*0.60"; y = "safeZoneY+safeZoneH*0.485"; w = "safeZoneW*0.085"; h = "safeZoneH*0.03"; action="private _ok=[] call TLB_CARP_fnc_runSolverSelfTest; hint format ['TLB CARP solver self-test: %1', if (_ok) then {'PASS'} else {'FAIL - check RPT'}]"; };
        class CopyDebug: RscButton { idc=IDC_TLB_CARP_COPY_DEBUG; text="COPY DEBUG"; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.520"; w = "safeZoneW*0.115"; h = "safeZoneH*0.03"; action="private _snapshot=[true] call TLB_CARP_fnc_debugSnapshot; copyToClipboard str _snapshot; hint 'TLB CARP debug snapshot copied/logged'"; };
        class CalRec: RscButton { idc=IDC_TLB_CARP_CAL_REC; text="CAL REC"; x = "safeZoneX+safeZoneW*0.44"; y = "safeZoneY+safeZoneH*0.520"; w = "safeZoneW*0.105"; h = "safeZoneH*0.03"; action="TLB_CARP_setting_calibrationRecorder=!TLB_CARP_setting_calibrationRecorder; [] call TLB_CARP_fnc_refreshPanel"; };
        class CopyCal: RscButton { idc=IDC_TLB_CARP_COPY_CAL; text="COPY LAST RUN"; x = "safeZoneX+safeZoneW*0.555"; y = "safeZoneY+safeZoneH*0.520"; w = "safeZoneW*0.13"; h = "safeZoneH*0.03"; action="[] call TLB_CARP_fnc_copyLastCalibrationRun"; };

        class Status: RscStructuredText { idc=IDC_TLB_CARP_STATUS; x = "safeZoneX+safeZoneW*0.315"; y = "safeZoneY+safeZoneH*0.560"; w = "safeZoneW*0.37"; h = "safeZoneH*0.220"; text=""; };
        class Close: RscButton { idc=-1; text="CLOSE"; x = "safeZoneX+safeZoneW*0.585"; y = "safeZoneY+safeZoneH*0.795"; w = "safeZoneW*0.10"; h = "safeZoneH*0.035"; action="private _d=findDisplay 9300; if (!isNull _d) then {_d closeDisplay 2}"; };
    };
};
