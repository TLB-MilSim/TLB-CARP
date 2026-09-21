class CfgPatches
{
	class usafdc_drop_computer
	{
		name="USAF CARP (Computed Air Release Point) System";
		author="USAF CARP Project";
		requiredVersion=2.1199999;
		// USAF_Cargo was required here until v0.12.1. v0.10.0 moved the whole release
		// sequence into fn_releaseCargo, so nothing in CARP needs USAF at runtime any
		// more -- but this line still refused to load the addon without it, which made
		// "CARP does not depend on the USAF mod" untrue in the only way a user notices.
		// Every remaining USAF touchpoint is guarded: fn_releaseSelected tests
		// isNil "USAF_CARGO_fnc_canDrop" before offering that path, and the cargo
		// manifest reads usaf_cargo as an object variable, which is absent rather than
		// broken when USAF is not loaded.
		requiredAddons[]=
		{
			"cba_main",
			"ace_interact_menu"
		};
		units[]={};
		weapons[]={};
	};
};
class CfgFunctions
{
	class USAFDC
	{
		tag="USAFDC";
		class lifecycle
		{
			file="\x\usafdc\addons\drop_computer\functions";
			class preInit
			{
				preInit=1;
			};
			class postInit
			{
				postInit=1;
			};
		};
		class generated
		{
			file="\x\usafdc\addons\drop_computer\functions\generated";
			class getModel
			{
			};
			class getTestVectors
			{
			};
		};
		class dz
		{
			file="\x\usafdc\addons\drop_computer\functions\dz";
			class getMissionDZs
			{
			};
			class beginMapDZ
			{
			};
			class setDZ
			{
			};
			class clearDZ
			{
			};
		};
		class aircraft
		{
			file="\x\usafdc\addons\drop_computer\functions\aircraft";
			class resolveAircraftProfile
			{
			};
			class getLoadedCargo
			{
			};
			class getAircraftState
			{
			};
			class projectAircraftKinematics
			{
			};
		};
		class ui
		{
			file="\x\usafdc\addons\drop_computer\functions\ui";
			class openPanel
			{
			};
			class refreshPanel
			{
			};
			class updateHud
			{
			};
			class updateMarkers
			{
			};
		};
		class auto
		{
			file="\x\usafdc\addons\drop_computer\functions\auto";
			class armAutoDrop
			{
			};
			class disarmAutoDrop
			{
			};
			class validateAutoDrop
			{
			};
			class triggerAutoDrop
			{
			};
			class sequenceCargo
			{
			};
		};
		class guidance
		{
			file="\x\usafdc\addons\drop_computer\functions\guidance";
			class buildWorldSolution
			{
			};
			class solveWorldReference
			{
			};
			class buildPlannedReference
			{
			};
			class interceptLimitDeg
			{
			};
			class computeRunInGuidance
			{
			};
			class confidenceReason
			{
			};
			class armGuidance
			{
			};
			class disarmGuidance
			{
			};
			class lockRunIn
			{
			};
			class unlockRunIn
			{
			};
			class updateGuidance
			{
			};
		};
		class solver
		{
			file="\x\usafdc\addons\drop_computer\functions\solver";
			class basisFromHeading
			{
			};
			class ballisticToTrigger
			{
			};
			class acquiredWindDisplacement
			{
			};
			class canopyTime
			{
			};
			class solveRelative
			{
			};
		};
		class debug
		{
			file="\x\usafdc\addons\drop_computer\functions\debug";
			class runSolverSelfTest
			{
			};
			class debugSnapshot
			{
			};
			class sampleWindTelemetry
			{
			};
			class sampleParachuteTelemetry
			{
			};
			class beginCalibrationRun
			{
			};
			class pollCalibrationRun
			{
			};
			class computeCalibrationError
			{
			};
			class formatCalibrationRun
			{
			};
			class copyLastCalibrationRun
			{
			};
			class buildDebugDropSolution
			{
			};
			class debugDropTest
			{
			};
			class debugDropSeries
			{
			};
			class copyLastDebugSeries
			{
			};
		};
	};
};
class RscDisplayEmpty;
class RscText;
class RscCombo;
class RscButton;
class RscCheckBox;
class RscEdit;
class RscStructuredText;
class USAFDC_RscDialog: RscDisplayEmpty
{
	idd=9300;
	movingEnable=0;
	enableSimulation=1;
	onLoad="uiNamespace setVariable ['USAFDC_display', _this # 0]; [] spawn {uiSleep 0.01; [] call USAFDC_fnc_refreshPanel};";
	onUnload="uiNamespace setVariable ['USAFDC_display', displayNull];";
	class controlsBackground
	{
		class Background: RscText
		{
			idc=-1;
			x="safeZoneX+safeZoneW*0.307";
			y="safeZoneY+safeZoneH*0.15";
			w="safeZoneW*0.386";
			h="safeZoneH*0.6295";
			colorBackground[]={0.027,0.043,0.055,0.96};
		};
		class Title: RscText
		{
			idc=-1;
			text="TLB CARP - COMPUTED AIR RELEASE POINT";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.162";
			w="safeZoneW*0.37";
			h="safeZoneH*0.034";
			font="RobotoCondensedBold";
			sizeEx=0.036;
			colorText[]={0.341,0.886,0.604,1};
			colorBackground[]={0,0,0,0};
		};
		class Eyebrow: RscText
		{
			idc=-1;
			text="TLB MISSION SYSTEMS";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.202";
			w="safeZoneW*0.37";
			h="safeZoneH*0.018";
			font="RobotoCondensed";
			sizeEx=0.022;
			colorText[]={0.553,0.604,0.639,1};
			colorBackground[]={0,0,0,0};
		};
	};
	class controls
	{
		class SecDROPZONE: RscText
		{
			idc=-1;
			text="DROP ZONE";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.238";
			w="safeZoneW*0.37";
			h="safeZoneH*0.021";
			font="RobotoCondensedBold";
			sizeEx=0.024;
			colorText[]={0.553,0.604,0.639,1};
			colorBackground[]={0,0,0,0};
		};
		class RuleDROPZONE: RscText
		{
			idc=-1;
			text="";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.26";
			w="safeZoneW*0.37";
			h="safeZoneH*0.0015";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.910,0.929,0.941,1};
			colorBackground[]={0.149,0.192,0.223,1};
		};
		class DZLabel: RscText
		{
			idc=-1;
			text="DZ";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.264";
			w="safeZoneW*0.078";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class DZCombo: RscCombo
		{
			idc=9301;
			x="safeZoneX+safeZoneW*0.397";
			y="safeZoneY+safeZoneH*0.264";
			w="safeZoneW*0.15";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
			onLBSelChanged="if (!USAFDC_state_panelRefreshing) then {private _m=(_this#0) lbData (_this#1); if (_m!='') then {private _d=[] call USAFDC_fnc_getMissionDZs; private _i=_d findIf {(_x#0) isEqualTo _m}; if (_i>=0) then {[(_d#_i)#2, (_d#_i)#1] call USAFDC_fnc_setDZ}; [] call USAFDC_fnc_refreshPanel}}";
		};
		class MapDZ: RscButton
		{
			idc=9302;
			text="SET ON MAP";
			x="safeZoneX+safeZoneW*0.551";
			y="safeZoneY+safeZoneH*0.264";
			w="safeZoneW*0.072";
			h="safeZoneH*0.03";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.341,0.886,0.604,1};
			action="private _d=findDisplay 9300; if (!isNull _d) then {_d closeDisplay 2}; [] call USAFDC_fnc_beginMapDZ";
		};
		class ClearDZ: RscButton
		{
			idc=9315;
			text="CLEAR";
			x="safeZoneX+safeZoneW*0.627";
			y="safeZoneY+safeZoneH*0.264";
			w="safeZoneW*0.058";
			h="safeZoneH*0.03";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.553,0.604,0.639,1};
			action="[] call USAFDC_fnc_clearDZ; [] call USAFDC_fnc_refreshPanel";
		};
		class SecMISSION: RscText
		{
			idc=-1;
			text="MISSION";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.312";
			w="safeZoneW*0.37";
			h="safeZoneH*0.021";
			font="RobotoCondensedBold";
			sizeEx=0.024;
			colorText[]={0.553,0.604,0.639,1};
			colorBackground[]={0,0,0,0};
		};
		class RuleMISSION: RscText
		{
			idc=-1;
			text="";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.334";
			w="safeZoneW*0.37";
			h="safeZoneH*0.0015";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.910,0.929,0.941,1};
			colorBackground[]={0.149,0.192,0.223,1};
		};
		class ModeLabel: RscText
		{
			idc=-1;
			text="MODE";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.338";
			w="safeZoneW*0.078";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class ModeCombo: RscCombo
		{
			idc=9303;
			x="safeZoneX+safeZoneW*0.397";
			y="safeZoneY+safeZoneH*0.338";
			w="safeZoneW*0.288";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
			onLBSelChanged="if (!USAFDC_state_panelRefreshing) then {private _v=(_this#0) lbData (_this#1); if (_v in ['TOUCHDOWN','CHUTE','JUMP']) then {[] call USAFDC_fnc_disarmAutoDrop; USAFDC_state_mode=_v; USAFDC_state_dropLatched=false}; [] call USAFDC_fnc_refreshPanel}";
		};
		class AircraftLabel: RscText
		{
			idc=-1;
			text="AIRCRAFT";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.374";
			w="safeZoneW*0.078";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class ProfileCombo: RscCombo
		{
			idc=9304;
			x="safeZoneX+safeZoneW*0.397";
			y="safeZoneY+safeZoneH*0.374";
			w="safeZoneW*0.288";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
			onLBSelChanged="if (!USAFDC_state_panelRefreshing) then {[] call USAFDC_fnc_disarmAutoDrop; USAFDC_state_profileOverride=(_this#0) lbData (_this#1); USAFDC_state_dropLatched=false; [] call USAFDC_fnc_refreshPanel}";
		};
		class TargetAglLabel: RscText
		{
			idc=-1;
			text="AGL m";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.41";
			w="safeZoneW*0.078";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class TargetAgl: RscEdit
		{
			idc=9320;
			text="3000";
			x="safeZoneX+safeZoneW*0.397";
			y="safeZoneY+safeZoneH*0.41";
			w="safeZoneW*0.06";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
		};
		class TargetGsLabel: RscText
		{
			idc=-1;
			text="GS km/h";
			x="safeZoneX+safeZoneW*0.467";
			y="safeZoneY+safeZoneH*0.41";
			w="safeZoneW*0.062";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class TargetGs: RscEdit
		{
			idc=9321;
			text="500";
			x="safeZoneX+safeZoneW*0.533";
			y="safeZoneY+safeZoneH*0.41";
			w="safeZoneW*0.055";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
		};
		class ApplyProfile: RscButton
		{
			idc=9322;
			text="APPLY";
			x="safeZoneX+safeZoneW*0.592";
			y="safeZoneY+safeZoneH*0.41";
			w="safeZoneW*0.093";
			h="safeZoneH*0.03";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.341,0.886,0.604,1};
			action="USAFDC_state_targetAglM=(parseNumber ctrlText ((findDisplay 9300) displayCtrl 9320)) max 300; USAFDC_state_targetGroundSpeedKmh=(parseNumber ctrlText ((findDisplay 9300) displayCtrl 9321)) max 100; [] call USAFDC_fnc_refreshPanel";
		};
		class SecENVIRONMENT: RscText
		{
			idc=-1;
			text="ENVIRONMENT";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.458";
			w="safeZoneW*0.37";
			h="safeZoneH*0.021";
			font="RobotoCondensedBold";
			sizeEx=0.024;
			colorText[]={0.553,0.604,0.639,1};
			colorBackground[]={0,0,0,0};
		};
		class RuleENVIRONMENT: RscText
		{
			idc=-1;
			text="";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.48";
			w="safeZoneW*0.37";
			h="safeZoneH*0.0015";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.910,0.929,0.941,1};
			colorBackground[]={0.149,0.192,0.223,1};
		};
		class WindLabel: RscText
		{
			idc=-1;
			text="WIND";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.484";
			w="safeZoneW*0.078";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class ManualWind: RscCheckBox
		{
			idc=9305;
			x="safeZoneX+safeZoneW*0.397";
			y="safeZoneY+safeZoneH*0.484";
			w="safeZoneW*0.022";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
			onCheckedChanged="if (!USAFDC_state_panelRefreshing) then {USAFDC_state_manualWind=(_this#1) isEqualTo 1; [] call USAFDC_fnc_refreshPanel}";
		};
		class WindSpeed: RscEdit
		{
			idc=9306;
			text="0";
			x="safeZoneX+safeZoneW*0.423";
			y="safeZoneY+safeZoneH*0.484";
			w="safeZoneW*0.055";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
		};
		class WindFrom: RscEdit
		{
			idc=9307;
			text="0";
			x="safeZoneX+safeZoneW*0.482";
			y="safeZoneY+safeZoneH*0.484";
			w="safeZoneW*0.055";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
		};
		class ApplyWind: RscButton
		{
			idc=9308;
			text="APPLY WIND";
			x="safeZoneX+safeZoneW*0.541";
			y="safeZoneY+safeZoneH*0.484";
			w="safeZoneW*0.144";
			h="safeZoneH*0.03";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.341,0.886,0.604,1};
			action="USAFDC_state_manualWindMs=0 max parseNumber ctrlText ((findDisplay 9300) displayCtrl 9306); USAFDC_state_manualWindFromDeg=(parseNumber ctrlText ((findDisplay 9300) displayCtrl 9307)) mod 360; [] call USAFDC_fnc_refreshPanel";
		};
		class SecJUMPRUN: RscText
		{
			idc=-1;
			text="JUMP RUN";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.532";
			w="safeZoneW*0.37";
			h="safeZoneH*0.021";
			font="RobotoCondensedBold";
			sizeEx=0.024;
			colorText[]={0.553,0.604,0.639,1};
			colorBackground[]={0,0,0,0};
		};
		class RuleJUMPRUN: RscText
		{
			idc=-1;
			text="";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.554";
			w="safeZoneW*0.37";
			h="safeZoneH*0.0015";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.910,0.929,0.941,1};
			colorBackground[]={0.149,0.192,0.223,1};
		};
		class StickLabel: RscText
		{
			idc=-1;
			text="STICK";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.558";
			w="safeZoneW*0.05";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class JumpStick: RscEdit
		{
			idc=9332;
			text="0";
			x="safeZoneX+safeZoneW*0.369";
			y="safeZoneY+safeZoneH*0.558";
			w="safeZoneW*0.048";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
		};
		class OpenLabel: RscText
		{
			idc=-1;
			text="OPEN m";
			x="safeZoneX+safeZoneW*0.427";
			y="safeZoneY+safeZoneH*0.558";
			w="safeZoneW*0.056";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class JumpOpen: RscEdit
		{
			idc=9333;
			text="0";
			x="safeZoneX+safeZoneW*0.487";
			y="safeZoneY+safeZoneH*0.558";
			w="safeZoneW*0.048";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
		};
		class JumpRun: RscButton
		{
			idc=9337;
			text="ARM JUMP RUN";
			x="safeZoneX+safeZoneW*0.539";
			y="safeZoneY+safeZoneH*0.558";
			w="safeZoneW*0.146";
			h="safeZoneH*0.03";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.957,0.757,0.365,1};
			tooltip="Arm or disarm the HALO exit cue: computed exit point, audible countdown and the jumplight. Was an ACE interaction until v0.15.0.";
			action="if (USAFDC_state_jumpArmed) then {['PILOT DISARM'] call USAFDC_fnc_disarmJumpRun} else {[] call USAFDC_fnc_armJumpRun}; [] call USAFDC_fnc_refreshPanel";
		};
		class SecCARGO: RscText
		{
			idc=-1;
			text="CARGO";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.606";
			w="safeZoneW*0.37";
			h="safeZoneH*0.021";
			font="RobotoCondensedBold";
			sizeEx=0.024;
			colorText[]={0.553,0.604,0.639,1};
			colorBackground[]={0,0,0,0};
		};
		class RuleCARGO: RscText
		{
			idc=-1;
			text="";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.628";
			w="safeZoneW*0.37";
			h="safeZoneH*0.0015";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.910,0.929,0.941,1};
			colorBackground[]={0.149,0.192,0.223,1};
		};
		class CargoLabel: RscText
		{
			idc=-1;
			text="DROP";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.632";
			w="safeZoneW*0.078";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.780,0.816,0.835,1};
			colorBackground[]={0,0,0,0};
		};
		class CargoCombo: RscCombo
		{
			idc=9312;
			x="safeZoneX+safeZoneW*0.397";
			y="safeZoneY+safeZoneH*0.632";
			w="safeZoneW*0.09";
			h="safeZoneH*0.03";
			font="RobotoCondensed";
			sizeEx=0.030;
			colorText[]={0.910,0.929,0.941,1};
			onLBSelChanged="if (!USAFDC_state_panelRefreshing) then {[] call USAFDC_fnc_disarmAutoDrop; USAFDC_state_cargoCount=parseNumber ((_this#0) lbData (_this#1)); USAFDC_state_dropLatched=false; [] call USAFDC_fnc_refreshPanel}";
		};
		class Jpads: RscButton
		{
			idc=9336;
			text="JPADS: OFF";
			x="safeZoneX+safeZoneW*0.491";
			y="safeZoneY+safeZoneH*0.632";
			w="safeZoneW*0.093";
			h="safeZoneH*0.03";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.910,0.929,0.941,1};
			tooltip="Steer the cargo canopy onto the drop zone after the chute opens. A stick is spread along the run-in rather than steered onto one point. Shared with the crew.";
			action="USAFDC_state_jpadsEnabled=!(missionNamespace getVariable ['USAFDC_state_jpadsEnabled',false]); [] call USAFDC_fnc_refreshPanel";
		};
		class Smoke: RscButton
		{
			idc=9331;
			text="SMOKE: ON";
			x="safeZoneX+safeZoneW*0.588";
			y="safeZoneY+safeZoneH*0.632";
			w="safeZoneW*0.097";
			h="safeZoneH*0.03";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.910,0.929,0.941,1};
			tooltip="Mark the released load with a coloured smoke shell under canopy, re-lit as each burns out. Shared with the crew.";
			action="USAFDC_state_smokeEnabled=!(missionNamespace getVariable ['USAFDC_state_smokeEnabled',true]); [] call USAFDC_fnc_refreshPanel";
		};
		class RuleActions: RscText
		{
			idc=-1;
			text="";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.68";
			w="safeZoneW*0.37";
			h="safeZoneH*0.0015";
			font="RobotoCondensed";
			sizeEx=0.03;
			colorText[]={0.910,0.929,0.941,1};
			colorBackground[]={0.149,0.192,0.223,1};
		};
		class RunIn: RscButton
		{
			idc=9309;
			text="RUN-IN";
			x="safeZoneX+safeZoneW*0.315";
			y="safeZoneY+safeZoneH*0.6915";
			w="safeZoneW*0.0895";
			h="safeZoneH*0.034";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.910,0.929,0.941,1};
			tooltip="Lock the aircraft's current ground track as the required drop heading.";
			action="if (USAFDC_state_runInLocked) then {[] call USAFDC_fnc_unlockRunIn} else {[] call USAFDC_fnc_lockRunIn}; [] call USAFDC_fnc_refreshPanel";
		};
		class Guidance: RscButton
		{
			idc=9310;
			text="GUIDANCE";
			x="safeZoneX+safeZoneW*0.4085";
			y="safeZoneY+safeZoneH*0.6915";
			w="safeZoneW*0.0895";
			h="safeZoneH*0.034";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.957,0.757,0.365,1};
			tooltip="Start solving and drawing the release point.";
			action="if (USAFDC_state_guidanceArmed) then {[] call USAFDC_fnc_disarmGuidance} else {[] call USAFDC_fnc_armGuidance}; [] call USAFDC_fnc_refreshPanel";
		};
		class Autopilot: RscButton
		{
			idc=9330;
			text="AP: OFF";
			x="safeZoneX+safeZoneW*0.502";
			y="safeZoneY+safeZoneH*0.6915";
			w="safeZoneW*0.0895";
			h="safeZoneH*0.034";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.910,0.929,0.941,1};
			tooltip="Fly the locked run-in at the target altitude and speed. Driver only.";
			action="if (missionNamespace getVariable ['USAFDC_state_apArmed',false]) then {['USER',false] call USAFDC_fnc_disarmAutopilot} else {[] call USAFDC_fnc_armAutopilot}; [] call USAFDC_fnc_refreshPanel";
		};
		class AutoDrop: RscButton
		{
			idc=9311;
			text="AUTO DROP: OFF";
			x="safeZoneX+safeZoneW*0.5955";
			y="safeZoneY+safeZoneH*0.6915";
			w="safeZoneW*0.0895";
			h="safeZoneH*0.034";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.898,0.302,0.251,1};
			tooltip="Release automatically at the computed release point.";
			action="if !(isNil 'USAFDC_fnc_armAutoDrop') then {if (USAFDC_state_autoArmed) then {[] call USAFDC_fnc_disarmAutoDrop} else {[] call USAFDC_fnc_armAutoDrop}}; [] call USAFDC_fnc_refreshPanel";
		};
		class Close: RscButton
		{
			idc=-1;
			text="CLOSE";
			x="safeZoneX+safeZoneW*0.595";
			y="safeZoneY+safeZoneH*0.7315";
			w="safeZoneW*0.09";
			h="safeZoneH*0.032";
			font="RobotoCondensedBold";
			sizeEx=0.028;
			colorText[]={0.949,0.420,0.420,1};
			action="private _d=findDisplay 9300; if (!isNull _d) then {_d closeDisplay 2}";
		};
	};
};
class RscTitles
{
	class USAFDC_HUD
	{
		idd=-1;
		movingEnable=0;
		enableSimulation=1;
		fadeIn=0;
		fadeOut=0;
		duration=1e+010;
		onLoad="uiNamespace setVariable ['USAFDC_HUD_display', _this # 0]; uiNamespace setVariable ['USAFDC_HUD_STEER', (_this # 0) displayCtrl 9402];";
		onUnload="uiNamespace setVariable ['USAFDC_HUD_display', displayNull]; uiNamespace setVariable ['USAFDC_HUD_STEER', controlNull];";
		class controls
		{
			class Guidance: RscStructuredText
			{
				idc=9401;
				x="safeZoneX + safeZoneW * 0.335";
				y="safeZoneY + safeZoneH * 0.035";
				w="safeZoneW * 0.33";
				h="safeZoneH * 0.17";
				text="";
				colorBackground[]={0.02,0.029999999,0.035,0.68000001};
			};
			class SteeringCenter: RscStructuredText
			{
				idc=9403;
				x="safeZoneX + safeZoneW * 0.4875";
				y="safeZoneY + safeZoneH * 0.205";
				w="safeZoneW * 0.025";
				h="safeZoneH * 0.035";
				text="<t align='center' size='1.2' color='#ffffff'>|</t>";
				colorBackground[]={0,0,0,0};
			};
			class SteeringCue: RscStructuredText
			{
				idc=9402;
				x="safeZoneX + safeZoneW * 0.4875";
				y="safeZoneY + safeZoneH * 0.205";
				w="safeZoneW * 0.025";
				h="safeZoneH * 0.035";
				text="<t align='center' size='1.25' color='#66e6a6'>^</t>";
				colorBackground[]={0,0,0,0};
			};
		};
	};
};
