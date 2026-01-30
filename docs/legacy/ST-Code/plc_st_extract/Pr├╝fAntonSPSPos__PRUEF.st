PROGRAM PRUEF
VAR

(* Basic Var Def's*)
   	EncoderSteps  			   		:  	 UINT	:= 4096;			(* 	EncoderSteps					*)
	Gear							:	REAL	:= -7.28;			(*	7.28/13.25 						*)
	Umfang							: 	REAL	:= 1.661;		(*	Umfang der Trommel in m			*)
	MaxUmdrehProMin				:	REAL	:= 4300;
	MaxUminInMotEinh				:	REAL	:= 21500;		(*	MaxUmdrehProMin / 0.2			*)

	SlaveGear						:	REAL	:= 4;			(* 	SlaveGear						*)
	SlaveScrewPitch					:	REAL	:= 0.004;		(*    	Steigung der Gewindespindel in m	*)
	EncoderSlave					:	REAL 	:= 4069;		          (* 	EncoderSlave					*)

    (*Engine*)
	ControlIN					AT%I*	:	UINT;     				(* 	In	ControlIN			von UI 		*)
	ControlIntern						:	UINT;				(* 									*)
	ControlOUT				AT%Q*	:	UINT;    				(* 	Out	SpeedSollOUT    PO1	to SEW 	*)
	GFMaster				AT%Q*	:	UINT 	 :=137;			(* 	Out	GFMaster	    PO5	to SEW 	*)
	GFSlave					AT%Q*	:	UINT  	:=1000;			(* 	Out	GFSlave		    PO6	to SEW 	*)
	VelOrPos				AT%I*	:	STRING  :='Vel';		(* 	In 0=Vel 1=Pos 2.. =Teufelszeug 		*)
	RampenformUI			AT%Q*	:	DWORD	:=0;
	PosSollUI				AT%I*	:	REAL  	:=0;			(*	 In   SollPos                     				*)
	PosWin					AT%I*	:	REAL  	:=0;

	SpeedSollIN				AT%I*	:	REAL  	:= 0.0;     	(*	In	SpeedSollIN			von UI  	*)
	SpeedSoll						:	REAL;				(* 		SpeedSoll					*)
	SetpPosBus				AT%Q*	:	DINT  	:= 0;     	(* 	Out	SpeedSollOUT    H422	to SEW  	*)
	SpeedIstMot				AT%I*	:	UINT;				(*	 In	SpeedIstMot		PI2	von SEW*)
	AccIN					AT%I*	:	REAL  	:= 5;     	(*	 In	AccIN				von UI  	*) (*not used*)
	DccIn					AT%I*	:	REAL  	:= 4;			(*	 In	DccIN				von ÜI 	*) (*not used*)
	AccTot					AT%I*	:	REAL  	:= 5.0;
	VelWin					AT%I*	:	REAL  	:= 0;

	MasterPosition 			AT%I*	:  	DINT;				(* 	In	Master Pos		ID2	von SEW*)

(* Positions *)
   	PosMaxHardUI			AT%I*	:	REAL  	:= 300.0;		(*	 In	PosMaxHardUI		von UI 	*)
   	PosMaxHardMOT					:	DWORD;				(* 		PosMaxHardMot				*)
	PosMaxUserUI			AT%I*	:	REAL  	:= 300.0;		(* 	In	PosMaxUserUI		von UI  *)
	PosMaxUserMot					:	DWORD;				(* 		PosMaxUserMot				*)
	PosMinUserUI			AT%I*	:	REAL  	:= -300.0;	(* 	In	PosMinUserUI		von UI  *)
	PosMinUserMot					:	DWORD;				(* 		PosMinUserMot				*)
	PosMinHardUI			AT%I*	:	REAL  	:= -300.0;	(* 	In	PosMinHardUI		von UI 	*)
	PosMinHardMot					:	DWORD;				(* 		PosMinHardMot				*)

	PosDiffG							:  	 REAL;  			(*zum Stoppen bei den Grenzpos		*)

(* Vel/Acc/Amp *)
	SpeedMaxUI				AT%I*	:	REAL  	:= 0.0;     	(*	 In	SpeedMaxUI			von UI 	*)
	SpeedMaxMot					:	REAL;				(* 		SpeedMaxMot					*)
	AccMaxUI				AT%I*	:	REAL  	:= 5.0;     	(*	 In	AccMaxUI			von UI 	*)
	DccMaxUI				AT%I*	:	REAL  	:= 5.0;		(*	 In	DccMaxUI			von UI 	*)
	AccMaxMot						:	REAL;				(* 		AccmaxMot					*)
	DccMaxMot						:	REAL;				(* 		DccmaxMot					*)

(* Filter *)
   	FilterP					AT%I*	:	REAL  	:= 0.01;	  		(*	 In	FilterP				von UI 	 *)
   	FilterI					AT%I*	:	REAL  	:= 0.0;	  		(*	 In	FilterI				von UI 	 *)
   	FilterD					AT%I*	:	REAL  	:= 0.0;	  		(* 	In	FilterD				von UI 	 *)
   	FilterIL					AT%I*	:	REAL  	:= 1.0;	  		(* 	In	FilterIL				von UI 	 *)

(* Rope *)
	RopeSWLL				AT%Q*	:	REAL  	:= 2000.0; 		(* Out	RopeSWLL	Const	to UI  	*)
	RopeDiameter			AT%Q*	:	REAL  	:= 5.0;    		(* Out	RopeDiam 	Const	to UI   	*)
	RopeType				AT%Q*	:	STRING	:= 'd';	(* Out	RopeType 	Const	to UI  	*)
	RopeNumber				AT%Q*	:	STRING	:= 'd'; 	(* Out	RopeNumber 	Const	to UI *)
	RopeLength				AT%Q*	:	REAL  	:= 200.0;  		(* Out	RopeLength 	Const	to UI   *)

(* Guide *)
	GuidePitchUI				AT%I*	:	REAL  	:= -6.3;  		 	(* In	Guide Pitch			von UI 		*)
	GuidePosMaxUI			AT%I*	:	REAL  	:= 0.992; 		(* In	Master PosMax		von UI 		*)
   	GuidePosMaxMot					:	REAL;				(* 		Master PosMax				*)
	GuidePosMinUI			AT%I*	:	REAL  	:= 0.0; 			(* In	Master PosMin		von UI  		*)
   	GuidePosMinMot					:	REAL;				(* 		Master PosMin				*)
	GuidePosManualMin				:	REAL  	:= 0.0;			(* Hart Kodierte Untere Grenze Guide		*)
	GuidePosManualMax				:	REAL  	:= 0.99;		(* Hart Kodierte Obere  Grenze Guide		*)
	GuidePosIstMotHI			AT%I*	:	UINT  	:= 0;			(* In	Guide PosHI		PI5	von SEW 	*)
	GuidePosIstMotHelp				:	DWORD;			(* 		GuideHelp					*)
	GuidePosIstMotLO		AT%I*	:	UINT  	:= 0;			(* In	Guide PosLO		PI6	von SEW 	*)

	GuidePosIstUI			AT%Q*	:	REAL  	:= 0;			(* Out	Guide Pos			to UI   	*)
	GuideStatus				AT%Q*	:	WORD;				(* Out	Guide Status		to UI  		*)
	GuideControl				AT%I*	:	UINT;				(* In 	Guide Control 		von UI  		*)
	GuideControlMot 			AT%Q*	:	UINT;				(* Out 	Guide Control 	PO4	to SEW  	*)
	GuideIstSpeed			AT%I*	:	UINT  	:= 0;			(* In	Guide Ist Speed PI7	von SEW 	*)
	GuideIstSpeedUI			AT%Q*	:	REAL  	:= 0;			(* Out	GuideIstSpeedUI		to UI   	*)
	GuideSollSpeed			AT%Q*	:	UINT  	:= 0;			(* Out 	Guide Control 	PO7	to SEW  	*)
	GuideSollSpeedUI		AT%I*	:	REAL  	:= 0;			(* In	GuideSollSpeed		von UI		*)
(* Status vars*)
	MasterMoment			AT%I*	:	UINT  	:= 0;			(* In	MasterMoment	PI3	von SEW 	*)
	CabTemperature			AT%I*	:	UINT  	:= 0;			(* In	CabTemperature	PI8	von SEW 	*)
	MotAuslast				AT%I*	:	UINT  	:= 0;			(* In	MotAuslast		PI10von SEW 	*)
	ActCur					AT%I*	:	UINT  	:= 0;			(* In	ActCur			PI10von SEW 	*)
	MasterAmpUI				AT%I*	:	REAL  	:= 100;			(* In 	MasterAmpUI 		von UI  		*)
	MasterAmp				AT%Q*	:	UINT;				(* Out	MasterAmp		PO3	to  SEW 	*)

(*Interne Variable*)
	PosSoll							:	REAL;
	PosSollD1						:	REAL;
	PosSollD2						:	REAL;
	PosSollD3						:	REAL;
	Count							:	INT		:=0;
	PosDiff							:	REAL;
	PosDiffInc						:	REAL;
	PosDiffIncMean					:	REAL;
	PosDiffIncFakt					:	REAL;
	PosStart							:	REAL;
	i								:	INT;
	Zeit								:	TON;
	Zykluszeit						:	TIME;
	ZykluszeitAlt						:	TIME;
	Intervall							:	TIME;
	c								:	BOOL;
	Speed							:	REAL	:=0;
  	SpeedSum						:	REAL;
	IntervallR						:	REAL;
	GuideDirection					:	REAL	:=1.0;
	MainDirection						:	REAL	:=1.0;
	Hold							:	REAL	:=0.0;
	Hold1							:	REAL	:=0.0;
	SpeedSollABS					:	REAL	:=0;

(*  SSPS Variablen *)
	PeriodicSelfCheck			AT%Q*	:	BOOL	:= FALSE;
	Positionsfenster			AT%Q*	:	BOOL	:= FALSE;
	Geschwindigkeit			AT%Q*	:	BOOL	:= FALSE;
	Endlage					AT%Q*	:	BOOL	:= FALSE;
	Encoder					AT%Q*	:	BOOL	:= TRUE;
	Steuerwort				AT%Q*	:	BOOL	:= FALSE;

(*PID Variable*)
	FilterPosDiffAlt					:	REAL;
	FilterSumPosDiff					:	REAL 	:= 0.0;
	FilterSpeed						:	REAL;
	FilterPos							:	REAL;

	SpeedMaxG						: 	REAL;		(*Maximal zulässige Geschwindigkeit.*)
	MasterPosINT					: 	DINT;

	PosIst							: 	REAL	:=0;
	SpeedIstUI 						: 	REAL	:=0;
	DeltaVel							:	 REAL;
	EstopReset				AT%I*	:	DWORD;
	PSetpPosBusDiff					:	DINT 	:= 0;
	PSetpBusPos			AT%I*	:	DINT 	:= 0;
	PSetpPosBusDiffMax				:	DINT 	:= 5000;
	PSetpPosBusErrorCount			:	INT	 	:= 0;
	PSetpPosBusErrorCountMax		:	INT	 	:= 10;
	PSetpPosBusErrorCountDecay  		    :	INT  	:= 10;
	PSetpDekrementCounter			: 	INT  	:= 0;
	PDecayTime						:	INT  	:= 5;

	MSetpPosBus			AT%Q*	:	DINT 	:= 0;

	TSBereit					AT%I*	:	BOOL 	:=FALSE;

	GuidePosIst11346			AT%I*	:	DINT	:=0;
	GuidePosIst						:	DINT	:=0;
	GuidePosIstFilter					:	DINT  :=0;
	GuidePosIstOld2					:	DINT	:=0;
	GuidePosIstOld1					:	DINT	:=0;
	GuidePosIstErwartet				:	DINT	:=0;
	MasterPosOld1					:	DINT	:=0;
	MasterPosOld2					:	DINT	:=0;
	MasterIstErwartet					:	DINT	:=0;
	MasterIstFilter						:	DINT	:=0;
	ECDataErrorFensterSlave			:	LREAL 	:= 16384.0;
	ECDataErrorCountSlave			:	DINT	:=0;
	ECDataErrorCountSlaveMax		:	INT	  	:= 3;
	ECDecayTimeDataSlave			:	INT		:= 50;
	ECDekrementCounterDataSlave		:	INT		:=0;
	ECDekrementCounterDataMaster	:	INT		:=0;
	ECDataErrorFensterMaster			:	LREAL 	:= 16384.0;
	ECDataErrorCountMaster			:	INT   	:= 0;
	ECDataErrorCountMasterMax		:	INT	  	:= 3;
	ECDecayTimeDataMaster			:	INT		:= 50;
	ECUmkehrMin					:	DINT 	:=0;
	ECUmkehrMax					:	DINT  	:=0;
	ECUmkehrDelta					:	DINT 	:=0;
	ECLagenSprung					:	BOOL 	:=FALSE;
	ECCycleCounter					:	INT  	:=0;
	ECLage							:	INT   	:=1;
	ECLageOld						:	INT	 	:=1;
	ECHoldTaster					:   	BOOL 	:= TRUE;
	ECWechseldauer					:	 INT		:=55;
	ECSlaveGefahren					:	DINT  	:=0;
	ECSyncPunkt						:	LREAL	:=0;
	Init								:	BOOL 	:=TRUE;
	GuidePosIstOld					:	DINT  :=0;
	ECDiffSlavePosMotPos			:	LREAL := 0.0;
	ECDiffSlavePosMotPosDiff			:	LREAL := 0.0;
	ECDiffSlavePosMotPosOld			:	LREAL := 0.0;
	ECDiffSlavePosMotPosOff			:	LREAL := 0.0;
	TotmannFahrbefehl		AT%I*	:	BOOL	:= FALSE;
	ECDekrementCounter				:	INT		:=0;
	ECSlaveMuteCounter				: 	 INT		:=0;
	ECMaxPosDiff					:	INT   :=4096;       (* Maximale PosDiff zwischen Motor und Leger *)
	ECMaxPosDiffWechsel				:	INT	  :=30000;
	ECPosDiffCount					:	INT   :=0;
	ECDecayTime					:	INT		:=200;

	GUINotHaltIN		AT%I*		:	BOOL	:=FALSE;
	GUINotHaltOUT	AT%Q*		:	BOOL	:=FALSE;
	SyncPosIstPosSoll :BOOL;
	RiseTotmann:R_TRIG;
END_VAR5(*BEGINN Reset*)
IF (EStopReset=1) THEN
	Positionsfenster			:= TRUE;
	Geschwindigkeit			:= TRUE;
	Endlage					:= TRUE;
	Encoder					:= TRUE;
	Steuerwort				:= TRUE;
	PSetpPosBusErrorCount      := 0;
END_IF
(*END Reset*)

(* BEGINN Periodic SelfCheck*)
	IF PeriodicSelfCheck = TRUE THEN
		PeriodicSelfCheck := FALSE;
	ELSE
		PeriodicSelfCheck := TRUE;
	END_IF
(* END  Periodic SelfCheck *)
RiseTotmann(CLK:=TotmannFahrbefehl, Q=>SyncPosIstPosSoll);
IF SyncPosIstPosSoll THEN
	PosSoll := PosIst;
END_IF
	PosSoll:= PosSoll+(Speed*IntervallR);

(* BEGINN Positions Fenster  *)
	MasterPosINT  		:= DWORD_TO_DINT(MasterPosition);
	PosIst  := ((MasterPosINT/Gear/EncoderSteps)*Umfang);	(* in m *)

	(*PosDiff :=  PosSollUI-PosIst;								(* in m  *)*)
	PosDiff:=PosSoll-PosIst;
	IF ABS(PosDiff) >= PosWin THEN
		Positionsfenster := FALSE;
	END_IF
(* END Positions Fenster  *)

(* BEGINN Messung Zykluszeit*)
	Zeit(IN := TRUE, PT := t#1d);
	Zykluszeit    	:= Zeit.ET;
	Intervall     	:= Zykluszeit-ZykluszeitAlt;
	ZykluszeitAlt 	:= Zykluszeit;
	IntervallR    	:= TIME_TO_DWORD(Intervall)/1000.0;
(* END Messung Zykluszeit *)

(*BEGINN  Bildung Steuerwort (SollGeschwindigkeit) BEGINN *)
	(* BEGINN Abfangen von zu großen Geschwindigkeiten  *)
		SpeedSoll := MIN(SpeedSollIN,SpeedMaxUI);
		SpeedSoll := MAX(SpeedSollIN,-SpeedMaxUI);
	(* END Abfangen von zu großen Geschwindigkeiten *)
	(* BEGINN Abfangen der Endpositionen *)
		(*BEGINN Bei Fahrt Richtung oberes Ende*)
			IF SpeedSoll >= 0 THEN
				PosDiffG := PosMaxUserUI - PosIst;				(* in m  *)
				IF PosDiffG > 0 THEN
					SpeedMaxG := SQRT(DccMaxUI*PosDiffG);
    					SpeedSoll := MIN(SpeedSoll,SpeedMaxG);
				ELSE
				IF SpeedSoll > 0 THEN
					SpeedSoll := 0.0;
				END_IF
				IF SpeedIstUI > 1 THEN
					Endlage := FALSE;
				END_IF
			END_IF
		(*END Bei Fahrt Richtung oberes Ende*)
			ELSE
		(*BEGINN  Bei Fahrt Richtung unteres Ende*)
				PosDiffG := PosIst - PosMinUserUI;				(* in m  *)
				IF PosDiffG > 0 THEN
					SpeedMaxG := SQRT(DccMaxUI*PosDiffG);
    					SpeedSoll := MAX(SpeedSoll,-SpeedMaxG);
				ELSE
					IF SpeedSoll < 0 THEN
						SpeedSoll := 0.0;
					END_IF
					IF SpeedIstUI < -1 THEN
						Endlage := FALSE;
					END_IF
				END_IF
			END_IF
		(*END Bei Fahrt Richtung unteres Ende *)
	(*END Abfangen der Endpositionen*)
	(* Überprüfung TwinSAFE Bereit Beginn *)
		IF TSBereit THEN
			SpeedSoll := SpeedSoll;
		ELSE
			SpeedSoll := 0;
		END_IF
	(* Überprüfung TWINSAFE Bereit End *)
	(*BEGINN RammpenGenerator mit AccTot*)
		IF (SpeedSoll > 0 AND SpeedSoll >= Speed) THEN
			Speed := Speed+AccTot*IntervallR;
			IF Speed > SpeedSoll THEN
				Speed := SpeedSoll;
			END_IF
		ELSIF (SpeedSoll >= 0 AND SpeedSoll < Speed) THEN
			Speed := Speed-AccTot*IntervallR;
			IF Speed < SpeedSoll THEN
				Speed := SpeedSoll;
			END_IF
		ELSIF (SpeedSoll <= 0 AND SpeedSoll < Speed) THEN
			Speed := Speed-AccTot*IntervallR;
			IF Speed < SpeedSoll THEN
				Speed := SpeedSoll;
			END_IF
		ELSIF (SpeedSoll <= 0 AND SpeedSoll >= Speed) THEN
			Speed := Speed+AccTot*IntervallR;
			IF Speed > SpeedSoll THEN
				Speed := SpeedSoll;
			END_IF
		END_IF
	(*END RampenGeneerator *)
	(*BEGINN Regler *)
		SpeedIstUI    		:= (UINT_TO_INT (SpeedIstMot)/Gear/300)*Umfang;		(* 0.2 Umdr./min --> m/s *)
		FilterSumPosDiff := FilterSumPosDiff*0.99+PosDiff*0.01;	(*Versuch anstatt einer Limitierung des SumPosDiff, oder einem Zeitfenster*)
		FilterSpeed      := FilterP*PosDiff + FilterI*(FilterSumPosDiff) + FilterD*(PosDiff-FilterPosDiffAlt);
		(*FilterSpeed in Steps/Intervall = FALSCH aber die Umrechnung ist konstant und in den FilterParametern berücksichtigt.*)
		FilterPosDiffAlt := PosDiff;
		SpeedSum := Speed + FilterSpeed;

		IF ABS(PosSollUI - PosIst) > 1.0 THEN
			SpeedSum := 0.5;
		END_IF

		DeltaVel := ABS(SpeedIstUI - SpeedSum);
	(*END Regler *)
	(* BEGINN Ueberpruefung Geschwindigkeits Fenster *)
		IF DeltaVel >= VelWin THEN
			Geschwindigkeit := FALSE;
		END_IF
	(*END Ueberpruefung Geschwindigkeits Fenster *)
	(*BEGINN Umrechnung in Motoreinheiten*)
		SpeedSum := SpeedSum / Umfang * Gear * 300;	(* Umrechnung von m/s auf 0.2 Umdr./min)  *)
		SpeedSum := MIN(SpeedSum,MaxUminInMotEinh);
		SpeedSum := MAX(SpeedSum,-MaxUminInMotEinh);
		IF SpeedSum <0 THEN
			SetpPosBus   := REAL_TO_INT (65535 + SpeedSum); (*Negativ Wert*)
		ELSE
		SetpPosBus   := REAL_TO_INT (SpeedSum);
		END_IF;
	MSetpPosBus := SetpPosBus;
	(*END Umrechnung Motoreinheiten*)
(* END Bildung Steuerwort (SollGeschwindigkeit)  *)

(*BEGINN Steuerwort (SollGeschwindigkeit) Ueberwachung *)
	PSetpPosBusDiff := ABS(SetpPosBus-PSetpBusPos);
	IF (PSetpPosBusDiff > PSetpPosBusDiffMax) AND (PSetpPosBusDiff < (65535- PSetpPosBusDiffMax)) THEN
		PSetpPosBusErrorCount := PSetpPosBusErrorCount +1;
	ELSE
		PSetpDekrementCounter := PSetpDekrementCounter +1;
	END_IF
	(*BEGINN Abklingen des PSetpPosBusErrorCount Fehlerzählers *)
		IF PSetpDekrementCounter >= PDecayTime THEN
			PSetpPosBusErrorCount := PSetpPosBusErrorCount -1;
			PSetpPosBusErrorCount := MAX(PSetpPosBusErrorCount,0);
			PSetpDekrementCounter :=0;
		END_IF
	(*END Abklingen des PSetpPosBusErrorCount Fehlerzählers *)
	IF PSetpPosBusErrorCount > PSetpPosBusErrorCountMax THEN
		Steuerwort				:= FALSE;
	END_IF
(*END Steuerwort (SollGeschwindigkeit) Ueberwachung *)

(*BEGINN Encoder Pruefung*)

	(*BEGINN Zu große oder zu kleine Umdrehpunkte abfangen*)
		GuidePosMinMot := GuidePosMinUI;
		GuidePosMaxMot := GuidePosMaxUI;
		IF GuidePosMinMot < GuidePosManualMin THEN
			GuidePosMinMot := GuidePosManualMin;
		END_IF
		IF GuidePosMaxMot > GuidePosManualMax THEN
			GuidePosMaxMot := GuidePosManualMax;
		END_IF
	(* Zu große oder zu kleine Umdrehpunkte abfangen END*)
		ECUmkehrMin 		:= REAL_TO_DINT(GuidePosMinUI*EncoderSlave*SlaveGear/SlaveScrewPitch);
		ECUmkehrMax 		:= REAL_TO_DINT(GuidePosMaxUI*EncoderSlave*SlaveGear/SlaveScrewPitch);
		ECUmkehrDelta 		:= ABS(ECUmkehrMax-ECUmkehrMin);
	(*BEGINN Data Initialisierung *)
		GuidePosIst :=GuidePosIst11346;
		IF Init OR (EStopReset=1) THEN
			GuidePosIstOld2 := GuidePosIst;
			GuidePosIstOld1 := GuidePosIst;
			MasterPosOld2   := MasterPosINT;
			MasterPosOld1   := MasterPosINT;
			ECDataErrorCountSlave :=0;
			ECDataErrorCountMaster :=0;
			Init := FALSE;
		END_IF
	(*END Data Initialisierung *)
	(*BEGINN Abklingzaehler Master Slave DataFilter*)
		ECDekrementCounterDataSlave  := ECDekrementCounterDataSlave+1;
		ECDekrementCounterDataMaster := ECDekrementCounterDataMaster+1;
	(*END Abklingzaehler Master Slave DataFilter*)
	(*BEGINN SlaveDataFilter*)
		GuidePosIstErwartet	:=REAL_TO_DINT(GuidePosIstOld1+(GuidePosIstOld1-GuidePosIstOld2)* GuideDirection);
		IF ABS(GuidePosIst-GuidePosIstErwartet) < ECDataErrorFensterSlave THEN
			GuidePosIstFilter := GuidePosIst;
		ELSE
			GuidePosIstFilter := GuidePosIstErwartet;
			ECDataErrorCountSlave:=ECDataErrorCountSlave+1;
		END_IF
		IF ECDataErrorCountSlave > ECDataErrorCountSlaveMax THEN
			Encoder := FALSE;
		END_IF
		IF  ECDekrementCounterDataSlave >= ECDecayTimeDataSlave THEN
			ECDataErrorCountSlave := ECDataErrorCountSlave -1;
			ECDataErrorCountSlave := MAX(ECDataErrorCountSlave,0);
			ECDekrementCounterDataSlave :=0;
		END_IF
	(*END SlsaveDataFilter*)
	(*BEGINN MasterDataFilter*)
		MasterIstErwartet   := MasterPosOld1+(MasterPosOld1-MasterPosOld2);
		IF ABS(MasterPosINT-MasterIstErwartet) < ECDataErrorFensterMaster THEN
			MasterIstFilter := MasterPosINT;
		ELSE
			MasterIstFilter :=  MasterIstErwartet;
			ECDataErrorCountMaster:=ECDataErrorCountMaster+1;
		END_IF
		IF ECDataErrorCountMaster > ECDataErrorCountMasterMax THEN
			Encoder := FALSE;
		END_IF
		IF ECDekrementCounterDataMaster >= ECDecayTimeDataMaster THEN
			ECDataErrorCountMaster := ECDataErrorCountMaster -1;
			ECDataErrorCountMaster := MAX(ECDataErrorCountMaster,0);
			ECDekrementCounterDataMaster :=0;
		END_IF
	(*END MasterDataFilter*)
	(*BEGINN Data Update*)
		GuidePosIstOld2	  := GuidePosIstOld1;
		GuidePosIstOld1   := GuidePosIstFilter;
		MasterPosOld2     := MasterPosOld1;
		MasterPosOld1     := MasterIstFilter;
	(*END Data Update*)
	(*BEGINNReversierbetrieb und Lagenzähler*)
		IF GuidePosIstFilter <= ECUmkehrMin AND Hold = 0.0 THEN
			IF GuideDirection < 0 THEN
				ECLage := ECLage+1;
				ECHoldTaster := FALSE;
			ELSE
				ECLage := ECLage-1;
				ECHoldTaster := FALSE;
			END_IF
			GuideDirection := GuideDirection*(-1);
			Hold:= 1.0;
		END_IF
		IF GuidePosIstFilter > ECUmkehrMin AND ECCycleCounter > ECWechseldauer THEN
			Hold:=0;
		END_IF
		IF GuidePosIstFilter >= ECUmkehrMax AND Hold1 =0.0 THEN
			IF GuideDirection > 0 THEN
				ECLage := ECLage+1;
				ECHoldTaster := FALSE;
			ELSE
				ECLage := ECLage-1;
				ECHoldTaster := FALSE;
			END_IF
			GuideDirection := GuideDirection*(-1);
			Hold1:=1.0;
		END_IF
		IF GuidePosIstFilter < ECUmkehrMax AND ECCycleCounter > ECWechseldauer THEN
			Hold1:=0.0;
		END_IF
		IF ECLageOld <> ECLage THEN
			ECCycleCounter := 0;
		ELSE
			ECCycleCounter := ECCycleCounter + 1;
		END_IF
   		GFMaster			:=REAL_TO_UINT((GuidePitchUI*(1/Gear*1000))*GuideDirection);
		ECLageOld := ECLage;
	(* END Reversierbetrieb und Lagenzaehler *)
	(* BEGINN Ermitteln wieweit ist Guider seit Lage1-ECUmkehrMin gefahren *)
		IF ECLage >0 THEN
			IF ECLage MOD 2 = 1 THEN
				ECSlaveGefahren  := ABS((ECLage-1)*ECUmkehrDelta+ ABS(GuidePosIstFilter));
			ELSE
				ECSlaveGefahren  := ABS((ECLage)*ECUmkehrDelta- ABS(GuidePosIstFilter));
			END_IF
		ELSIF ECLage =0 THEN
			ECSlaveGefahren  := -ABS(GuidePosIstFilter);
		ELSE
			IF ABS(ECLage) MOD 2 = 1 THEN
				ECSlaveGefahren  := -ABS((ECLage-1)*ECUmkehrDelta+ ABS(GuidePosIstFilter));
			ELSE
				ECSlaveGefahren  := -ABS((ECLage)*ECUmkehrDelta- ABS(GuidePosIstFilter));
			END_IF
		END_IF
	(*END Ermitteln wieweit ist Guider seit Lage1-ECUmkehrMin gefahren *)
	(*BEGINN Synchronpunkt *)
	IF ECCycleCounter = ECWechseldauer THEN									(* Nach Lagenwechsel Neues Offset *)
		ECSyncPunkt := ECDiffSlavePosMotPos;
	END_IF
	(*END Synchronpunkt *)

	(*BEGINN Encoder Plausibilitaets Pruefung und Synchronfahrt *)
		IF TotmannFahrbefehl = TRUE THEN											(* Wenn Taster gedruekt wird dann -> *)
			IF ECHoldTaster THEN
				ECSyncPunkt  := 0;
			END_IF

		IF ABS(SpeedSoll) > 0.2 THEN												(* Wenn gefahren wird  ->*)
			IF (GuidePosIstFilter-GuidePosIstOld <> 0) THEN							(* unterrscheidet sich	die Letzte
																				GuidePositionn von der jetzigen
																				(wir sind nicht im "mute"-Bereich) -> *)
				ECDekrementCounter := ECDekrementCounter +1;						(* Zaehler fuer abklingen der PosFehler *)
				ECSlaveMuteCounter :=0;											(* Zaehler fuer "mute"-Bereich *)
		(*BEGINN Ueberwachung ist der Guider innerhalb des Erlaubten Bereichs ? *)
				IF GuidePosIstFilter < (ECUmkehrMin - ECMaxPosDiffWechsel) OR			(* Wenn wir nicht innerhalb des *)
					GuidePosIstFilter > (ECUmkehrMax + ECMaxPosDiffWechsel) THEN	(* Bewegungsbereichs sind*)
					Encoder := FALSE;													(* NOT-HALT *)
				END_IF
		(*END Ueberwachung ist der Guider innerhalb des Erlaubten Bereichs ? *)
			(*BEGINN Gangueberwachung *)
				ECDiffSlavePosMotPos := (ECSlaveGefahren)*(Gear/GuidePitchUI)-		(*Gangunterschied zwischen Slave *)
									      (MasterPosINT)-ECDiffSlavePosMotPosOff;     	(*und Master mit Offset zum Beginn des
																				Taster drueken *)
				ECDiffSlavePosMotPosDiff := ECSyncPunkt - ECDiffSlavePosMotPos;		(* Lagenwechsel*)
																				(* Innerhalb der Lage kleine Grenze *)
				IF ECCycleCounter > ECWechseldauer THEN							(* Wenn wir innerhalb der Lage verfahren*)
					IF ABS(ECDiffSlavePosMotPosDiff) > ECMaxPosDiff THEN			(* Vergleich mit kleiner Grenze *)
						ECPosDiffCount:=ECPosDiffCount+1;
					END_IF
				ELSE
																				(* Lagenwechsel Große Grenze *)
					IF ABS(ECDiffSlavePosMotPosDiff) > ECMaxPosDiffWechsel THEN	(* Wenn wir beim Lagenwechsel sind *)
						ECPosDiffCount:=ECPosDiffCount+1;							(* Vergleich mit groeserer Grenze*)
					END_IF
				END_IF
				IF ECPosDiffCount >= 10 THEN										(* Wenn Anzahl der Fehler zu hoch -> *)
					Encoder := FALSE;													(* NOT-HALT *)
				END_IF
			(*END Gangueberwachung *)
				(*BEGINN Abklingen des Fehlerzählers*)
				IF ECDekrementCounter >= ECDecayTime THEN
					ECPosDiffCount := ECPosDiffCount -1;
					ECPosDiffCount := MAX(ECPosDiffCount,0);
					ECDekrementCounter :=0;
				END_IF
				(*END Abklingen des Fehlerzählers*)
		(*BEGINN  Data Update*)
				GuidePosIstOld :=GuidePosIstFilter;
		(*END Data Update *)
			ELSE																	(* wir sind im "mute"-Bereich *)
				ECSlaveMuteCounter := ECSlaveMuteCounter +1;
				IF ECSlaveMuteCounter >= 15 THEN
					Encoder := FALSE;
				END_IF
			END_IF																	(* if "mute"-Bereich END *)
		END_IF																		(* if "fahren" END *)
	ELSE																			(* Taster nicht gedrueckt *)
		ECPosDiffCount :=0;															(* Fehlerzaehler *)
		GuidePosIstOld :=GuidePosIstFilter-1;										(* fangen nicht im "mute"-Bereich an *)
		ECDiffSlavePosMotPosOff := (ECSlaveGefahren)*(Gear/GuidePitchUI)			(* Offset *)
								-(MasterPosINT);
		ECCycleCounter :=0;
		ECDekrementCounter :=0;
		ECSlaveMuteCounter :=0;
		ECHoldTaster := TRUE;
	END_IF
(* END Encoder Plausibilitaets Pruefung und Synchronfahrt *)
(* BEGINN Weiterreichung GUI Not-Halt an TwinSAFE*)
	GUINotHaltOUT := GUINotHaltIN;
(* END Weiterreichung GUI Not-Halt an TwinSAFE*)
CTUD@
DELETE@
F_TRIG@
FIND@
INSERT@
LEFT@	LEN@	MID@
R_TRIG@
REPLACE@
RIGHT@RS@
PRUEF.SyncPosIstPosSoll
