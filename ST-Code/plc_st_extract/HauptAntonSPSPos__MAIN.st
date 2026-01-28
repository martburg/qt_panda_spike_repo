PROGRAM MAIN
VAR

(* Basic Var Def's*)
    EncoderSteps					:   UINT := 4096;		(* 	EncoderSteps					*)
	Gear							:	REAL := -7.28;		(*	7.28/13.25 						*)
	Umfang							: 	REAL := 1.661;		(*	Umfang der Trommel in m			*)
	MaxUmdrehProMin					:	REAL := 4300;
	MaxUminInMotEinh				:	REAL := 21500;		(*	MaxUmdrehProMin / 0.2			*)
	SpeedMaxforUI			AT%Q*	: 	REAL := 0;			(*	SpeedMaxforUI begrenzt V eingabe	*)
	PosDifforUI				AT%Q*	:	REAL := 0;

	SlaveGear						:	REAL := 4;			(* 	SlaveGear						*)
	SlaveScrewPitch					:	REAL := 0.004;		(*  Steigung der Gewindespindel in m	*)
	EncoderSlave					:	REAL := 4069;		(* 	EncoderSlave					*)


(* LifeTickvariables*)
    LifetickUItx			AT%Q*	:	UINT := 0;			(* 	Out	LifetickUItx		to UI   		*)
	LifetickUIrx			AT%I*	:  	UINT := 0;			(* 	In	LifetickUIrx		von UI 		*)
	LifetickDiff			AT%Q*	:	UINT := 0;			(* 	Out	LifetickDiff		to UI  		*)

    (*Engine*)
	GeartoUI				AT%Q*	:	REAL;				(* 	Out	Gear		Const	to UI  	*)
    Name					AT%Q*	:	STRING:= 'Anton';	 	(* 	Out	Name		Const	to UI  	*)
	StatusvonSEW			AT%I*	:	UINT  := 0;     			(* 	In	StatusvonSEW	PI1	von SEW*)
	StatusnachUI			AT%Q*	:	UINT  := 0;     			(* 	Out	StatusnachUI		to UI  		*)
	ControlIN				AT%I*	:	UINT;     				(* 	In	ControlIN			von UI 		*)
	ControlIntern					:	UINT;				(* 									*)
	ControlOUT				AT%Q*	:	UINT;    				(* 	Out	SpeedSollOUT    PO1	to SEW 	*)
	GFMaster				AT%Q*	:	UINT  :=137;			(* 	Out	GFMaster	    PO5	to SEW 	*)
	GFSlave					AT%Q*	:	UINT  :=1000;			(* 	Out	GFSlave		    PO6	to SEW 	*)
	VelOrPos				AT%I*	:	STRING  :='Vel';		(* 	In 0=Vel 1=Pos 2.. =Teufelszeug 		*)
	RampenformUI			AT%Q*	:	DWORD	:=0;
	PosSollUI				AT%I*	:	REAL  :=0;			(*	 In   SollPos                     				*)


	SpeedSollIN				AT%I*	:	REAL  := 0.0;     		(*	In	SpeedSollIN			von UI  	*)
	SpeedSoll						:	REAL;				(* 		SpeedSoll					*)
	SetpPosBus				AT%Q*	:	DINT  := 0;     	(* 	Out	SpeedSollOUT    H422	to SEW  	*)
	PSetpPosBus				AT%Q*	:	DINT  := 0;     	(* 	Out	SpeedSollOUT    to Pruef  	*)
	SpeedIstMot				AT%I*	:	UINT;				(*	 In	SpeedIstMot		PI2	von SEW*)
	SpeedIstUI				AT%Q*	:	REAL  := 0.0;	  		(* 	Out	SpeedIstUI 			to UI   	*)
	AccIN					AT%I*	:	REAL  := 5;     			(*	 In	AccIN				von UI  	*) (*not used*)
	DccIn					AT%I*	:	REAL  := 4;			(*	 In	DccIN				von ÜI 	*) (*not used*)
	AccTot					AT%I*	:	REAL  :=5.0;
	VelWin					AT%I*	:	REAL  := 0.5;
	MasterPosition			AT%I*	:  	DINT;				(* 	In	Master Pos		ID2	von SEW*)
	PosIst					AT%Q*	:	REAL  := 0.0;    		(* 	Out	PosIst 				to UI  	*)
(* Positions *)
    PosMaxHardUI			AT%I*	:	REAL  := 300.0;		(*	 In	PosMaxHardUI		von UI 	*)
    PosMaxHardMOT					:	DWORD;			(* 		PosMaxHardMot				*)
	PosMaxUserUI			AT%I*	:	REAL  := 300.0;		(* 	In	PosMaxUserUI		von UI  	*)
	PosMaxUserMot					:	DWORD;			(* 		PosMaxUserMot				*)
	PosMinUserUI			AT%I*	:	REAL  := -300.0;		(* 	In	PosMinUserUI		von UI  	*)
	PosMinUserMot					:	DWORD;			(* 		PosMinUserMot				*)
	PosMinHardUI			AT%I*	:	REAL  := -300.0;		(* 	In	PosMinHardUI		von UI 	*)
	PosMinHardMot					:	DWORD;			(* 		PosMinHardMot				*)
	PosWin					AT%I*	:	REAL  := 0.5;

	PosDiffG						:  	 REAL;  				(*zum Stoppen bei den Grenzpos		*)

(* Vel/Acc/Amp *)
	SpeedMaxUI				AT%I*	:	REAL  := 0.0;     		(*	 In	SpeedMaxUI			von UI 	*)
	SpeedMaxMot						:	REAL;				(* 		SpeedMaxMot				*)
	AccMaxUI				AT%I*	:	REAL  := 5.0;     		(*	 In	AccMaxUI			von UI 	*)
	DccMaxUI				AT%I*	:	REAL  := 5.0;			(*	 In	DccMaxUI			von UI 	*)
	AccMaxMot						:	REAL;				(* 		AccmaxMot					*)
	DccMaxMot						:	REAL;				(* 		DccmaxMot					*)


(* Filter *)
    FilterP					AT%I*	:	REAL  := 1;	  		(*	 In	FilterP				von UI 	 *)
    FilterI					AT%I*	:	REAL  := 0.0;	  		(*	 In	FilterI				von UI 	 *)
   	FilterD					AT%I*	:	REAL  := 0.0;	  		(* 	In	FilterD				von UI 	 *)
   	FilterIL				AT%I*	:	REAL  := 1.0;	  		(* 	In	FilterIL				von UI 	 *)

(* Rope *)
	RopeSWLL				AT%Q*	:	REAL  := 2000.0; 		(* Out	RopeSWLL	Const	to UI  	*)
	RopeDiameter			AT%Q*	:	REAL  := 6.0;    		(* Out	RopeDiam 	Const	to UI   	*)
	RopeType				AT%Q*	:	STRING:= ' ';			(* Out	RopeType 	Const	to UI  	*)
	RopeNumber				AT%Q*	:	STRING:= ' '; 			(* Out	RopeNumber 	Const	to UI *)
	RopeLength				AT%Q*	:	REAL  := 200.0;  		(* Out	RopeLength 	Const	to UI   *)

(* Guide *)
	GuidePitchUI			AT%I*	:	REAL  := -6.3;  		(* In	Guide Pitch			von UI 		*)
	GuidePosMaxUI			AT%I*	:	REAL  := 0.992; 	(* In	Master PosMax		von UI 		*)
    GuidePosMaxMot					:	REAL;				(* 		Master PosMax				*)
	GuidePosMinUI			AT%I*	:	REAL  := 0.0; 		(* In	Master PosMin		von UI  		*)
    GuidePosMinMot					:	REAL;				(* 		Master PosMin				*)
	GuidePosManualMin				:	REAL  := 0.0;		(* Hart Kodierte Untere Grenze Guide		*)
	GuidePosManualMax				:	REAL  := 0.99;		(* Hart Kodierte Obere  Grenze Guide		*)
	GuidePosManualMaxUI		AT%Q*	:	REAL  := 0.990;		(* Hart Kodierte Grenze für UI				*)
	GuidePosIstMotHI		AT%I*	:	UINT  := 0;			(* In	Guide PosHI		PI5	von SEW 	*)
	GuidePosIstMotHelp				:	DWORD;			(* 		GuideHelp					*)
	GuidePosIstMotLO		AT%I*	:	UINT  := 0;			(* In	Guide PosLO		PI6	von SEW 	*)
	GuidePosIst						:	DINT;				(* 		Guide PosINT			   	*)
	GuidePosIstFilter				:	DINT  :=0;
	GuidePosIstOld1					:	DINT  :=0;
	GuidePosIstOld2					:	DINT  :=0;
	GuidePosIstErwartet				:	DINT  :=0;
	GuidePosIstOld					:	DINT  :=0;
	GuidePosIst11346		AT%I*	:	DINT  :=0;
	GuidePosIstUI			AT%Q*	:	REAL  := 0;			(* Out	Guide Pos			to UI   	*)
	GuideStatus				AT%Q*	:	WORD;				(* Out	Guide Status		to UI  		*)
	GuideControl			AT%I*	:	UINT;				(* In 	Guide Control 		von UI  		*)
	GuideControlMot			AT%Q*	:	UINT;				(* Out 	Guide Control 	PO4	to SEW  	*)
	GuideIstSpeed			AT%I*	:	UINT  := 0;			(* In	Guide Ist Speed PI7	von SEW 	*)
	GuideIstSpeedUI			AT%Q*	:	REAL  := 0;			(* Out	GuideIstSpeedUI		to UI   	*)
	GuideSollSpeed			AT%Q*	:	UINT  := 0;			(* Out 	Guide Control 	PO7	to SEW  	*)
	GuideSollSpeedUI		AT%I*	:	REAL  := 0;			(* In	GuideSollSpeed		von UI		*)
(* Status vars*)
	MasterMoment			AT%I*	:	UINT  := 0;			(* In	MasterMoment	PI3	von SEW 	*)
	MasterMomentUI			AT%Q*	:	REAL  := 0;			(* Out	MasterMomentUI		to UI   	*)

	CabTemperature			AT%I*	:	UINT  := 0;			(* In	CabTemperature	PI8	von SEW 	*)
	CabTemperatureUI		AT%Q*	:	REAL  := 0;			(* Out	CabTemperatureUI	to UI   	*)

	MotAuslast				AT%I*	:	UINT  := 0;			(* In	MotAuslast		PI10von SEW 	*)
	MotAuslastUI			AT%Q*	:	REAL  := 0;			(* Out	MotAuslastUI		to UI   		*)

	ActCur					AT%I*	:	UINT  := 0;			(* In	ActCur			PI10von SEW 	*)
	ActCurUI				AT%Q*	:	REAL  := 0;			(* Out	ActCurUI			to UI   		*)

	MasterAmpUI				AT%I*	:	REAL  := 100;			(* In 	MasterAmpUI 		von UI  		*)
	MasterAmp				AT%Q*	:	UINT;				(* Out	MasterAmp		PO3	to  SEW 	*)

(*Interne Variable*)
	PosSoll							:	REAL;
	PosSollD1						:	REAL;
	PosSollD2						:	REAL;
	PosSollD3						:	REAL;
	Count							:	INT:=0;
	PosDiff							:	REAL;
	PosDiffInc						:	REAL;
	PosDiffIncMean					:	REAL;
	PosDiffIncFakt					:	REAL;
	PosStart						:	REAL;
	i								:	INT;
	Zeit							:	TON;
	Zykluszeit						:	TIME;
	ZykluszeitAlt					:	TIME;
	Intervall						:	TIME;
	c								:	BOOL;
	SPEED							:	REAL :=0;
    SpeedSum						:	REAL;
	IntervallR						:	REAL;
	GuideDirection					:	REAL :=1.0;
	MainDirection					:	REAL:=1.0;
	Hold							:	REAL:=0.0;
	Hold1							:	REAL:=0.0;
	SpeedSollABS					:	REAL:=0;

(*  SSPS Variablen *)
	PeriodicSelfCheck		AT%Q*	:	BOOL	:= FALSE;
	Positionsfenster		AT%Q*	:	BOOL	:= FALSE;
	Geschwindigkeit			AT%Q*	:	BOOL	:= FALSE;
	Endlage					AT%Q*	:	BOOL	:= FALSE;
	Encoder					AT%Q*	:	BOOL	:= FALSE;
	TotmannFahrbefehl		AT%I*	:	BOOL	:= FALSE;

(* Variable Für Fehlerbehandlung*)
	Input					AT%I*	:	DWORD ; 			(* In	Input		 	ID2 von SEW 		*)
	StatusMaster			AT%I*	:	UINT;				(* In	StatusMaster	PI1 von SEW 			*)
	StatusSlave				AT%I*	:	UINT;				(* In	StatusSlave		PI4 von SEW 		*)

(*PID Variable*)
	FilterPosDiffAlt				:	REAL;
	FilterSumPosDiff				:	REAL := 0.0;
	FilterSpeed						:	REAL;
	FilterPos						:	REAL;


	SpeedMaxG						: 	REAL;		(*Maximal zulässige Geschwindigkeit.*)
	MasterPosINT					: 	DINT;
(*SDO Trial Beginn *)
	Rampenform						:	DWORD:=0;
	ReadSdo							:	FB_EcCoESdoRead;

	Write_DataSollwertPA2			:	DWORD:=0;   (* KeineFunktion*)
	WriteSdo						:	FB_EcCoESdoWrite;

	IllegalRampenform				:	DWORD:=3; (* Positionsinterpolation 16bit=10 VelInterpolation = 8 *)
	VelInterpolation				:	DWORD:=8;
	PosInterpolation12bit			:	DWORD:=9;

	PosFilterSum					:	REAL :=0.0;
	FIFO							:	DELAY;
	Filterlength					:	INT :=3;

	ECDiffSlavePosMotPos			:	LREAL := 0.0;		(*  Geberplausibilität Differenz SlavePosition MotorPosition*)
	ECDiffSlavePosMotPosDiff		:	LREAL := 0.0;
	ECDiffSlavePosMotPosOld			:	LREAL := 0.0;
	ECDiffSlavePosMotPosOff			:	LREAL := 0.0;		(*  Geberplausibilität Diff SlavePosition MotorPosition Offset*)
(* Filterund Max Beschleunigung sichern Beginn *)
	(*Slave*)
	ECDataErrorFensterSlave			:	LREAL 	:= 16384.0;    (* ist von Max Beschl abhängig entspricht 4mm vorschub*)
	ECDataErrorCountSlave			:	INT   	:= 0;
	ECDataErrorCountSlaveMax		:	INT	  	:= 3;
	ECDecayTimeDataSlave			:	INT		:= 50;

	(*Master*)
	ECDataErrorFensterMaster		:	LREAL 	:= 16384.0;    (* ist von Max Beschl abhängig entspricht 4mm vorschub*)
	ECDataErrorCountMaster			:	INT   	:= 0;
	ECDataErrorCountMasterMax		:	INT	  	:= 3;
	ECDecayTimeDataMaster			:	INT		:= 50;


	ECMaxPosDiff					:	INT   :=4096;       (* Maximale PosDiff zwischen Motor und Leger *)
	ECMaxPosDiffWechsel				:	INT	  :=30000;
	ECPosDiffCount					:	INT   :=0;
	ECHelper						:	LREAL :=0.0;
	ECSlaveGefahren					:	DINT  :=0;
	ECFaktor						:	LREAL :=0.0;
	ECLage							:	INT   :=1;
	ECUmkehrMin						:	DINT  :=0;
	ECUmkehrMax						:	DINT  :=0;
	ECUmkehrDelta					:	DINT  :=0;
	ECLagenSprung					:	BOOL  :=FALSE;
	ECCycleCounter					:	INT   :=0;
	ECLageOld						:	INT	  :=1;
	ECWechseldauer					:   INT		:=55;
	ECSyncPunkt						:	LREAL	:=0;
	ECDekrementCounter				:	INT		:=0;
	ECDecayTime						:	INT		:=200;
	ECDekrementCounterDataSlave		:	INT		:=0;
	ECDekrementCounterDataMaster	:	INT		:=0;

	ECSlaveMuteCounter				:   INT		:=0;

	MasterPosOld1					:	DINT	:=0;
	MasterPosOld2					:	DINT	:=0;
	MasterIstErwartet				:	DINT	:=0;
	MasterIstFilter					:	DINT	:=0;

	Init							:	BOOL	:= TRUE;
	ECHoldTaster					:   BOOL 	:= TRUE;

	MSetpBusPos			AT%I*		:	DINT	:= 0;
	MSetpPosBusDiff					:	DINT	:= 0;
	MSetpPosBusDiffMax				:	DINT	:= 5000;
	MSetpPosBusErrorCount			:	INT		:= 0;
	MSetpPosBusErrorCountMax		:	INT		:= 10;
	MSetpBusPosErrorCountDecay		:	INT		:= 10;
	MSetpDekrementCounter			:	INT		:= 0;
	MDecayTime						:	INT		:= 5;
	Steuerwort			AT%Q*		:	BOOL	:= FALSE;


	TSBereit			AT%I*		:	BOOL	:= FALSE;

	GUINotHaltIN		AT%I*		:	BOOL	:=FALSE;
	GUINotHaltOUT	AT%Q*		:	BOOL	:=FALSE;
	SyncPosIstPosSoll :BOOL;
	RiseTotmann:R_TRIG;
	PosDiffPosSollPosSollUI:REAL;

END_VARWN(* Variable nach UI Beginn*)
	StatusnachUI		:=StatusMaster;(*init Vars*)
	GeartoUI			:=Gear;
	MasterMomentUI		:=UINT_TO_INT(MasterMoment);
	CabTemperatureUI	:=UINT_TO_INT(CabTemperature);
	MotAuslastUI		:=UINT_TO_INT(MotAuslast);
	ActCurUI			:=UINT_TO_INT(ActCur);
	GuideStatus			:=StatusSlave;
	(* MasterPos Skalierung von EncoderSteps auf m Beginn *)
		MasterPosINT  		:= DWORD_TO_DINT(MasterPosition);
		PosIst       		:= ((MasterPosINT/Gear/EncoderSteps)*Umfang);	(* in m *)
	(* MasterPos Skalierung End *)
	(* GuidePos Skalierung von Encoder Steps auf m Beginn *)
		GuidePosIstMotHelp 	:=SHL(WORD_TO_DWORD(GuidePosIstMotHI),16)+GuidePosIstMotLO;
		GuidePosIst			:= GuidePosIst11346;
	(* Zu große oder zu kleine Umdrehpunkte abfangen BEGINN*)
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
	IF ResetSSPSVars THEN
		Positionsfenster		:= TRUE;
		Geschwindigkeit			:= TRUE;
		Endlage					:= TRUE;
		Encoder					:= TRUE;
		Steuerwort				:= TRUE;
		MSetpPosBusErrorCount      := 0;
	END_IF
(* Daten Filter und Maximale Beschleunigung sichern BEGINN*)
	(* Data Initialisieren BEGINN *)
	IF Init OR ResetSSPSVars THEN
		GuidePosIstOld2 := GuidePosIst;
		GuidePosIstOld1 := GuidePosIst;
		MasterPosOld2   := MasterPosINT;
		MasterPosOld1   := MasterPosINT;
		ECDataErrorCountSlave :=0;
		ECDataErrorCountMaster :=0;
		Init := FALSE;
	END_IF
	(* Data Initialisieren END ---- Zaehler BEGINN*)
	ECDekrementCounterDataSlave  := ECDekrementCounterDataSlave+1;
	ECDekrementCounterDataMaster := ECDekrementCounterDataMaster+1;
	(* Zaehler END ---- Slave BEGINN *)
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
	(* Slave END ---- Master BEGINN*)
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
	(* Master END ---- Data update BEGINN*)
	GuidePosIstOld2	  := GuidePosIstOld1;
	GuidePosIstOld1   := GuidePosIstFilter;
	MasterPosOld2     := MasterPosOld1;
	MasterPosOld1     := MasterIstFilter;
(* Daten Filter und Maximale Beschleunigung sichern BEGINN*)

	GuidePosIstUI	  := GuidePosIst/EncoderSlave/SlaveGear*SlaveScrewPitch;
	(* GuidePos Skalierung End *)
	(* MasterVel Skalierung auf m/s) Beginn *)
		SpeedIstUI    		:= (UINT_TO_INT (SpeedIstMot)/Gear/300)*Umfang;		(* 0.2 Umdr./min --> m/s *)
	(* MasterVel Skalierung End *)
	(* SpeedMax für UI Begrenzung Beginn*)
		SpeedMaxforUI := MaxUmdrehProMin/Gear/60*Umfang;
	(* SpeedMax für UI Begrenzung End*)
	(* GuideVel Skalierung auf m/s) Beginn *)
		GuideIstSpeedUI 	:=(UINT_TO_INT(GuideIstSpeed)/SlaveGear/300)*SlaveScrewPitch;
	(* GuideVel Skalierung End *)
(* Variable nach UI End *)
(* Variable nach SEW Beginn *)
	Masteramp			:= REAL_TO_UINT(MasterAmpUI*10);
(* Variable nach SEW End *)

(* Vel or Pos Modus Beginn*)
	IF StatusnachUI = 4356 THEN
		IF VelOrPos = 'Pos' THEN
			IF WriteSdo.bBusy = FALSE THEN
				WriteSdo(bexecute:=TRUE);
			ELSE
				WriteSdo(
					sNetId:='172.16.17.1.3.1',
					nSlaveAddr:=1010,
					nIndex:=8632,		(*P916*)
					nSubIndex:=0,
					pSrcBuf:=ADR(PosInterpolation12bit),
					cbBufLen:=4,
					bExecute:=FALSE,
					tTimeout:=T#500ms);
			END_IF
		ELSIF VelOrPos = 'Vel' THEN
			IF WriteSdo.bBusy = FALSE THEN
				WriteSdo(bexecute:=TRUE);
			ELSE
				WriteSdo(
					sNetId:='172.16.17.1.3.1',
					nSlaveAddr:=1010,
					nIndex:=8632,		(*P916*)
					nSubIndex:=0,
					pSrcBuf:=ADR(VelInterpolation),
					cbBufLen:=4,
					bExecute:=FALSE,
					tTimeout:=T#500ms);
			END_IF
		ELSE
			IF WriteSdo.bBusy = FALSE THEN
				WriteSdo(bexecute:=TRUE);
			ELSE
				WriteSdo(
					sNetId:='172.16.17.1.3.1',
					nSlaveAddr:=1010,
					nIndex:=8632,		(*P916*)
					nSubIndex:=0,
					pSrcBuf:=ADR(IllegalRampenform),
					cbBufLen:=4,
					bExecute:=FALSE,
					tTimeout:=T#500ms);
			END_IF
		END_IF
	END_IF
(* SDO Read P916 Rampenform Beginn *)
	IF ReadSdo.bBusy = FALSE THEN
		ReadSdo(bexecute:=TRUE);
	ELSE
		ReadSdo(
			sNetId:='172.16.17.1.3.1',
			nSlaveAddr:=1010,
			nIndex:=8632,		(*P916*)
			nSubIndex:=0,
			pDstBuf:=ADR(Rampenform),
			cbBufLen:=4,
			bExecute:=FALSE,
			tTimeout:=T#500ms);
	END_IF
	RampenformUI := Rampenform;
(* SDO Read P916 Rampenform End *)

(* Reversierbetrieb und Lagenzaehler BEGINN*)
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
(* Reversierbetrieb und Lagenzaehler END *)
(* Ermitteln wieweit ist Guider seit Lage1-ECUmkehrMin gefahren BEGINN *)
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
(* Ermitteln wieweit ist Guider seit Lage1-ECUmkehrMin gefahren BEGINN *)
(* Synchronpunkt BEGINN *)
	IF ECCycleCounter = ECWechseldauer THEN										(* Nach Lagenwechsel Neues Offset *)
		ECSyncPunkt := ECDiffSlavePosMotPos;
	END_IF
(* Synchronpunkt END *)

(* Encoder Plausibilitaets Pruefung und Synchronfahrt BEGINN *)

IF TotmannFahrbefehl = TRUE THEN												(* Wenn Taster gedruekt wird dann -> *)
	GuideControlMot     := GuideControl;											(* Einkuppeln *)
	IF ECHoldTaster THEN
		ECSyncPunkt  := 0;
	END_IF

	IF ABS(SpeedSoll) > 0.2 THEN												(* Wenn gefahren wird  ->*)
		IF (GuidePosIstFilter-GuidePosIstOld <> 0) THEN								(* unterrscheidet sich	die Letzte
																				   GuidePositionn von der jetzigen
																				   (wir sind nicht im "mute"-Bereich) -> *)
			ECDekrementCounter := ECDekrementCounter +1;							(* Zaehler fuer abklingen der PosFehler *)
			ECSlaveMuteCounter :=0;													(* Zaehler fuer "mute"-Bereich *)
	(* Ueberwachung ist der Guider innerhalb des Erlaubten Bereichs BEGINN *)
			IF GuidePosIstFilter < (ECUmkehrMin - ECMaxPosDiffWechsel) OR		(* Wenn wir nicht innerhalb des *)
				GuidePosIstFilter > (ECUmkehrMax + ECMaxPosDiffWechsel) THEN	(* Bewegungsbereichs sind*)
				Encoder := FALSE;													(* NOT-HALT *)
			END_IF
	(* Ueberwachung ist der Guider innerhalb des Erlaubten Bereichs END *)
	(* Gangueberwachung BEGINN *)
			ECDiffSlavePosMotPos := (ECSlaveGefahren)*(Gear/GuidePitchUI)-			(*Gangunterschied zwischen Slave *)
									(MasterPosINT)-ECDiffSlavePosMotPosOff;     	(*und Master mit Offset zum Beginn des
																					Taster drueken *)
			ECDiffSlavePosMotPosDiff := ECSyncPunkt - ECDiffSlavePosMotPos;			(* Lagenwechsel
																					 *)
		(* Innerhalb der Lage kleine Grenze *)
			IF ECCycleCounter > ECWechseldauer THEN								(* Wenn wir innerhalb der Lage verfahren*)
				IF ABS(ECDiffSlavePosMotPosDiff) > ECMaxPosDiff THEN				(* Vergleich mit kleiner Grenze *)
					ECPosDiffCount:=ECPosDiffCount+1;
				END_IF
			ELSE
		(* Lagenwechsel Große Grenze *)																(* Wenn wir beim Lagenwechsel sind *)
				IF ABS(ECDiffSlavePosMotPosDiff) > ECMaxPosDiffWechsel THEN			(* Vergleich mit groeserer Grenze*)
					ECPosDiffCount:=ECPosDiffCount+1;
				END_IF
			END_IF
			IF ECPosDiffCount >= 10 THEN										(* Wenn Anzahl der Fehler zu hoch -> *)
				Encoder := FALSE;													(* NOT-HALT *)
			END_IF
		(* Abklingen des Fehlerzählers BEGINN *)
			IF ECDekrementCounter >= ECDecayTime THEN
				ECPosDiffCount := ECPosDiffCount -1;
				ECPosDiffCount := MAX(ECPosDiffCount,0);
				ECDekrementCounter :=0;
			END_IF
		(* Abklingen des Fehlerzählers END --- Data Update BEGINN*)
			GuidePosIstOld :=GuidePosIstFilter;
		(* Data Update END *)
		ELSE																	(* wir sind im "mute"-Bereich *)
			ECSlaveMuteCounter := ECSlaveMuteCounter +1;
			IF ECSlaveMuteCounter >= 15 THEN
				Encoder := FALSE;
			END_IF
		END_IF																	(* if "mute"-Bereich END *)
	END_IF																		(* if "fahren" END *)
ELSE																			(* Taster nicht gedrueckt *)
	GuideControlMot:= 2;														(* Auskuppeln (reset) *)
	ECPosDiffCount :=0;															(* Fehlerzaehler *)
	GuidePosIstOld :=GuidePosIstFilter-1;										(* fangen nicht im "mute"-Bereich an *)
	ECDiffSlavePosMotPosOff := (ECSlaveGefahren)*(Gear/GuidePitchUI)			(* Offset *)
								-(MasterPosINT);
	ECCycleCounter :=0;
	ECDekrementCounter :=0;
	ECSlaveMuteCounter :=0;
	ECHoldTaster := TRUE;

END_IF
(* Encoder Plausibilitaets Pruefung und Synchronfahrt END *)


(* Guide Manual Grenzen Beginn*)
	IF GuideSollSpeedUI >=0 THEN
		GuideSollSpeed 		:= REAL_TO_UINT(MIN(GuideSollSpeedUI,MaxUmdrehProMin));
	END_IF
	IF GuideSollSpeedUI <0 THEN
		GuideSollSpeed 		:= REAL_TO_UINT(MAX(GuideSollSpeedUI,-MaxUmdrehProMin));
	END_IF
	IF GuidePosIstUI < GuidePosManualMin AND GuideSollSpeedUI < 0 THEN
		GuideSollSpeed	:= 0;
	END_IF
	IF GuidePosIstUI > GuidePosManualMax AND GuideSollSpeedUI > 0 THEN
		GuideSollSpeed	:= 0;
	END_IF
(* Guide Manual Grenzen End*)

PosMaxHardMot 		:= REAL_TO_INT ((PosMaxHardUI*Gear*EncoderSteps)/Umfang);
PosMaxUserMot 		:= REAL_TO_INT ((PosMaxUserUI*Gear*EncoderSteps)/Umfang);
PosMinUserMot 		:= REAL_TO_INT ((PosMinUserUI*Gear*EncoderSteps)/Umfang);
PosMinHardMot 		:= REAL_TO_INT ((PosMinHardUI*Gear*EncoderSteps)/Umfang);


SpeedMaxMot 		:= SpeedMaxUI/Umfang*Gear*300;					(* m/s --> 0.2 Umdr./min *)
AccMaxMot   		:= AccMaxUI;									(* m/s-->  Umdr./Zykluszeit*)
DccMaxMot			:= DccMaxUI;
(* AmpMaxMot  		:= AmpMaxUI .... Prozent von MaxAmpSEW *)
(*ControlIntern 		:= ControlIn;*)

(* Generate Rising Edge for TON Function*)
IF ControlIntern = 1 THEN
	c := TRUE;
ELSE
	c := FALSE;
END_IF

(*Call TON mit ablaufdatum 1Tag später*)
Zeit(IN := c, PT := t#1d);

(*Messung Zykluszeit*)
	Zykluszeit    	:= Zeit.ET;
	Intervall     	:= Zykluszeit-ZykluszeitAlt;
	ZykluszeitAlt 	:= Zykluszeit;
	IntervallR    	:= TIME_TO_DWORD(Intervall)/1000.0;

(* Hauptprozess *)
RiseTotmann(CLK:=TotmannFahrbefehl, Q=>SyncPosIstPosSoll);
IF SyncPosIstPosSoll THEN
	PosStart := PosIst;
	PosSoll  := PosStart;
END_IF

(* Abfangen von zu großen Geschwindigkeiten Beginn *)
	SpeedSoll := MIN(SpeedSollIN,SpeedMaxUI);
	SpeedSoll := MAX(SpeedSollIN,-SpeedMaxUI);
(* Abfangen von zu großen Geschwindigkeiten End *)


(* Abfangen der Endpositionen *)
	(* Bei Fahrt Richtung oberes Ende Beginn*)
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
	(* Bei Fahrt Richtung oberes Ende End*)
ELSE
	(* Bei Fahrt Richtung unteres Ende Beginn*)
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
	(* Bei Fahrt Richtung unteres Ende End *)
(* Abfangen der Endpositionen End*)

(* Lifetick auswerten Beginn *)
	(* Lifetick wird hier in SPS generiert im UI gespiegelt und differenz zwischen tx und rx abgefragt*)
	LifetickUItx := LifetickUItx +1;
	LifetickDiff := LifetickUItx - LifetickUIrx;
IF TotmannFahrbefehl THEN
	IF LifetickDiff > 150 AND LifetickDiff<65425 THEN
		ControlIntern := 0;
	ELSE
		ControlIntern := 1;
		IF PeriodicSelfCheck = TRUE THEN
			PeriodicSelfCheck := FALSE;
		ELSE
			PeriodicSelfCheck := TRUE;
		END_IF
	END_IF
ELSE
	IF LifetickDiff > 1500 AND LifetickDiff<64075 THEN
		ControlIntern := 0;
	ELSE
		ControlIntern := 1;
		IF PeriodicSelfCheck = TRUE THEN
			PeriodicSelfCheck := FALSE;
		ELSE
			PeriodicSelfCheck := TRUE;
		END_IF
	END_IF
END_IF

(* Lifetick auswerten End *)

IF Rampenform = 8 AND TRUE THEN
(* GESCHWINDIGKEITSMODUS*)
	(* Überprüfung TwinSAFE Bereit Beginn *)
	IF TSBereit THEN
		SpeedSoll := SpeedSoll;
	ELSE
		SpeedSoll := 0;
	END_IF
	(* Überprüfung TWINSAFE Bereit End *)
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
    	(* Filter ___________________________________________________________________________________________*)
		(* Pos Soll wird jetzt aus VelUI gerechnet ueberlegung posSoll aus PosSolUI Nehmen*)
	PosSoll := PosSoll+(Speed*IntervallR);  				(* in m + m/Zykluszeit*)
	(*PosSoll := PosSollUI;*)
	PosDiff := PosSoll-PosIst;								(* in m  *)
	PosDiffPosSollPosSollUI := PosSoll-PosSollUI;
	IF ABS(PosDiff) >= PosWin THEN
		Positionsfenster := FALSE;
	END_IF
	PosDifforUI := PosSollUI-PosIst;
	FilterSumPosDiff := FilterSumPosDiff*0.99+PosDiff*0.01;	(*Versuch anstatt einer Limi de SumPosD, oder einem Zeitfenster*)
	FilterSpeed      := FilterP*PosDiff + FilterI*(FilterSumPosDiff) + FilterD*(PosDiff-FilterPosDiffAlt);

		(*FilterSpeed in Steps/Intervall = FALSCH aber die Umrechnung ist konst und in den FilterParametern berücksichtigt.*)
	FilterPosDiffAlt := PosDiff;
	SpeedSum := Speed + FilterSpeed;

	IF ABS(PosSoll - PosIst) > 1.0 THEN
		SpeedSum := 0.5;
	END_IF

	IF ABS(SpeedIstUI - SpeedSum) >= VelWin THEN
		Geschwindigkeit := FALSE;
	END_IF
		(* Bis hier in SI-Einheiten: [m/s] *)
	SpeedSum := SpeedSum / Umfang * Gear * 300;	(* Umrechnung von m/s auf 0.2 Umdr./min)  *)
	SpeedSum := MIN(SpeedSum,MaxUminInMotEinh);
	SpeedSum := MAX(SpeedSum,-MaxUminInMotEinh);
	(*Generate Steuerwort*)
	IF SpeedSum <0 THEN
		SetpPosBus   := REAL_TO_INT (65535 + SpeedSum);
	ELSE
		SetpPosBus   := REAL_TO_INT (SpeedSum);
	END_IF;
	PSetpPosBus := SetpPosBus;
ELSIF Rampenform <> 8 THEN
(* Undefinierte Rampenform*)
		ControlIntern :=0;
END_IF

IF TotmannFahrbefehl = TRUE AND ControlIntern = 1 THEN
	ControlOUT:= 2#0000_0000_0000_0110;
ELSIF TotmannFahrbefehl = FALSE AND ControlIN = 64 THEN
	ControlOUT := 64;
ELSE
	ControlOUT:= 0;
END_IF;
(* Steuerwort (SollGeschwindigkeit) Ueberwachung Beginn *)
MSetpPosBusDiff := ABS(SetpPosBus-MSetpBusPos);
IF (MSetpPosBusDiff > MSetpPosBusDiffMax) AND (MSetpPosBusDiff < ( 65535- MSetpPosBusDiffMax)) THEN
	MSetpPosBusErrorCount := MSetpPosBusErrorCount +1;
ELSE
	MSetpDekrementCounter := MSetpDekrementCounter +1;
END_IF
(* Abklingen des PSetpPosBusErrorCount Fehlerzählers BEGINN *)
IF MSetpDekrementCounter >= MDecayTime THEN
	MSetpPosBusErrorCount := MSetpPosBusErrorCount -1;
	MSetpPosBusErrorCount := MAX(MSetpPosBusErrorCount,0);
	MSetpDekrementCounter :=0;
END_IF
(* Abklingen des PSetpPosBusErrorCount Fehlerzählers END *)
IF MSetpPosBusErrorCount > MSetpPosBusErrorCountMax THEN
	Steuerwort				:= FALSE;
END_IF
(* END Steuerwort (SollGeschwindigkeit) Ueberwachung *)
(* BEGINN Weiterreichung GUI Not-Halt an TwinSAFE*)
	GUINotHaltOUT := GUINotHaltIN;
(* END Weiterreichung GUI Not-Halt an TwinSAFE*)

		(*Sanfte Beschleunigung rechnen  SpeedSoll [m/S] --> Speed [m/S]  *)
		(* Ohne Dcc ( nur Acc) Beginn *)
		(*IF Speed<SpeedSoll THEN
			Speed := Speed+AccMaxMot*IntervallR;
			IF Speed>SpeedSoll THEN
				Speed := SpeedSoll;
			END_IF
		ELSE
			Speed := Speed-AccMaxMot*IntervallR;
			IF Speed<SpeedSoll THEN
				Speed := SpeedSoll;
			END_IF
		END_IF*)
		(* Ohne Dcc ( nur Acc) End *)


	(*IF WriteSdo.bBusy = FALSE THEN
		WriteSdo(bexecute:=TRUE);
	ELSE
		WriteSdo(
			sNetId:='172.16.17.2.2.1',
			nSlaveAddr:=1007,

			nIndex:=8632,		(*Rampenform *)
			nSubIndex:=0,

			pSrcBuf:=ADR(Write_DataRampenform),
			cbBufLen:=4,

			bExecute:=FALSE,
			tTimeout:=T#500ms);

	END_IF*)

		(*PosDiff := PosSollUI-PosIst;								(* in m  *)
		(*PosDiff := PosSollUI;*)
		PosDifforUI := PosDiff;

		FilterSumPosDiff := FilterSumPosDiff*0.99+PosDiff*0.01;	(*Versuch
 anstatt einer Limitierung des SumPosDiff, oder einem Zeitfenster*)
		FilterSpeed      := FilterP*PosDiff + FilterI*(FilterSumPosDiff) + FilterD*(PosDiff-FilterPosDiffAlt);
		(*FilterSpeed in Steps/Intervall = FALSCH aber die Umrechnung ist konstant und in den FilterParametern
 berücksichtigt.*)
		FilterPosDiffAlt := PosDiff;

		(*FilterSpeed := 0;*)
		SpeedSum := FilterSpeed;

		(* Bis hier in SI-Einheiten: [m/s] *)
		SpeedSum := SpeedSum / Umfang * Gear * 300;	(* Umrechnung von m/s auf 0.2 Umdr./min)  *)

j
		SpeedSum := MIN(SpeedSum,MaxUminInMotEinh);
		SpeedSum := MAX(SpeedSum,-MaxUminInMotEinh);
	(*Generate Steuerwort*)
		IF SpeedSum <0 THEN
			ControlOUT := 2#0000_0000_0000_0110;  (*3079;*)

			SetpPosBus   := REAL_TO_INT (65535 + SpeedSum);
			(* Hier bauen wir künstlich einen negativen Geschwindigkeitswert der funktioniert, obwohl der SEW keine
negativen Sollgeschwindigkeiten annimmt.*)
		ELSE
			ControlOUT := 2#0000_0000_0000_0110;  (*2567;*)
			SetpPosBus   := REAL_TO_INT (SpeedSum);
		END_IF;*)
