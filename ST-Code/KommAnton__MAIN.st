PROGRAM MAIN

VAR CONSTANT
		LOCAL_HOST_IP				: STRING(15) 		:= '172.16.17.2';
		LOCAL_HOST_PORT1			: UDINT				:= 15001;
		REMOTE_HOST_IP				: STRING(15) 		:= '172.16.17.5';
		REMOTE_HOST_PORT1			: UDINT 			:= 15002;
END_VAR
VAR
    	fbSocketCloseAll 				: 	FB_SocketCloseAll;
    	bCloseAll 						: 	BOOL := TRUE;
		nErrIdA							: 	UDINT;
		fbPeerToPeer1					: 	FB_PeerToPeerBuffer;
    	sendFifo1						: 	FB_FifoBuffer;
    	receiveFifo1					: 	FB_FifoBuffer;
    	sendToEntry1					: 	ST_FifoEntryBuffer;
    	entryReceivedFrom1				: 	ST_FifoEntryBuffer;
		DatenArray						:	ARRAY[0..352] OF BYTE;
		PtDaten							:	POINTER TO BYTE;
		iDatenArray						:	INT:=0;
		iDownDaten						:	INT:=0;
		StrOffset						: 	UINT;

(* Austauschvariable mit HauptSPS *)
	(*SocketServer Teil Beginn*)
		Modus							:	STRING	:='xx';
		OwnPID							:	STRING	:='0000';
		ControlPID  					:	STRING	:='0000';
		ControlPIDTx					:	UINT	:=0;
		Intent							:	STRING	:='xx';
		Enable							:	BOOL	:=FALSE;
		LTOld							:	UINT	:= 0;
	(*SocketServer Teil End*)
		VelOrPos				AT%Q*	:	STRING	:= 'VEL';
		LifetickUItx			AT%I*	:	UINT 	:= 0;
		LifetickUIrx			AT%Q*	:	UINT 	:= 0;
		LifetickDiff			AT%I*	:	UINT	:= 0;
		LifetickDiff1					:	UINT	:= 0;

   		Name					AT%I*	:	STRING 	:= '';
		Status					AT%I*	:	UINT 	:= 0;
		ControlIN				AT%Q*	:	UINT	:= 0;
		PControlIN				AT%Q*	:	UINT	:= 0;


		SpeedSollIN				AT%Q*	:	REAL	:=0;
		PSpeedSollIN			AT%Q*	:	REAL	:=0;
		SpeedIstUI				AT%I*	:	REAL	:=0;
		sCutVel							:	STRING	:='0.00000';
		AccIN					AT%Q*	:	REAL	:=5;
		PAccIN					AT%Q*	:	REAL	:=5;
		DccIN					AT%Q*	:	REAL	:=4;
		PDccIN					AT%Q*	:	REAL	:=4;

		PosIst					AT%I*	:	REAL	:=0;
		sCutPos							:	STRING	:='0.00000';
		PosSoll					AT%Q*	:	REAL	:=0;
		PPosSoll				AT%Q*	:	REAL	:=0;

    	PosMaxHardUI			AT%Q*	:	REAL	:=300.0;
		PPosMaxHardUI			AT%Q*	:	REAL	:=300.0;
		PosMaxUserUI			AT%Q*	:	REAL	:=300;
		PPosMaxUserUI			AT%Q*	:	REAL	:=300.0;
		PosMinUserUI			AT%Q*	:	REAL	:=0;
		PPosMinUserUI			AT%Q*	:	REAL	:=0.0;
		PosMinHardUI			AT%Q*	:	REAL	:=0;
		PPosMinHardUI			AT%Q*	:	REAL	:=0.0;
		PosWinUI				AT%Q*	:	REAL	:=0.5;
		PPosWinUI				AT%Q*	:	REAL	:=0.0;

		SpeedMaxUI				AT%Q*	:	REAL	:=0;
		PSpeedMaxUI				AT%Q*	:	REAL	:=0;
		AccMaxUI				AT%Q*	:	REAL	:=5;
		PAccMaxUI				AT%Q*	:	REAL	:=5;
		DccMaxUI				AT%Q*	:	REAL	:=5;
		PDccMaxUI				AT%Q*	:	REAL	:=5;
		AmpMaxUI				AT%Q*	:	REAL	:=100;
		PAmpMaxUI				AT%Q*	:	REAL	:=100;
		AccTotUI				AT%Q*	:	REAL	:=5.00;
		PAccTotUI				AT%Q*	:	REAL	:=5;
		VelWinUI				AT%Q*	:	REAL	:=0.5;
		PVelWinUI				AT%Q*	:	REAL	:=0.5;
		(*AmpMaxMot							:	REAL;*)

    (* Filter *)
    	FilterP					AT%Q*	:	REAL	:=1;
		PFilterP				AT%Q*	:	REAL	:=1;
    	FilterI					AT%Q*	:	REAL	:=0;
		PFilterI				AT%Q*	:	REAL	:=0;
    	FilterD					AT%Q*	:	REAL	:=0;
		PFilterD				AT%Q*	:	REAL	:=0;
    	FilterIL				AT%Q*	:	REAL	:=1;
		PFilterIL				AT%Q*	:	REAL	:=300.0;

    (* Rope *)
		RopeSWLL				AT%I*	:	REAL	:=2000;
		RopeDiameter			AT%I*	:	REAL	:=6.0;
		RopeType				AT%I*	:	STRING	:='d';
		RopeNumber				AT%I*	:	STRING	:='d';
		RopeLength				AT%I*	:	REAL	:=300;

    (* Guide *)
		GuidePitchUI			AT%Q*	:	REAL	:=-6.3;
		PGuidePitchUI			AT%Q*	:	REAL	:=-6.3;
		GuidePosMaxUI			AT%Q*	:	REAL	:=0.96;
		PGuidePosMaxUI			AT%Q*	:	REAL	:=0.096;
		GuidePosManualMaxUI		AT%I*	:	REAL	:=0.096;
		GuidePosMinUI			AT%Q*	:	REAL	:=0;
		PGuidePosMinUI			AT%Q*	:	REAL	:=0;
		GuidePosIstUI			AT%I*	:	REAL	:=0;
		GuideStatus				AT%I*	:	WORD;
		GuideControl			AT%Q*	:	UINT;   			(* Geht zum Main *)
		PGuideControl			AT%Q*	:	UINT;
		GuideControlUI					:	UINT;			(* Kommt vom UI wird bei Notaus auf '2' gesetzt um neu zu Synchronisieren*)
		GuideIstSpeedUI			AT%I*	:	REAL;
		GuideSollSpeedUI		AT%Q*	:	REAL;
		PGuideSollSpeedUI		AT%Q*	:	REAL;

		MasterMomentUI			AT%I*	:	REAL;
		CabTemperatureUI		AT%I*	:	REAL;
		MotAuslastUI			AT%I*	:	REAL;
		ActCurUI				AT%I*	:	REAL;
		GearToUI				AT%I*	:	REAL;
		SpeedMaxforUI			AT%I*	:	REAL;
		PosDiffForUI			AT%I*	:	REAL;

		RampenformUI			AT%I*	:   DWORD;

		SystemTime						:	STRING(25):='E_0000-00-00-00:00:00.000';
		AmsIDFrederik						: T_AmsNetID		:= '172.16.17.6.1.1';
		tzID									: E_TimeZoneID	:= eTimeZoneID_Invalid;
		fbTime								:FB_LocalSystemTime:= (bEnable 	:= TRUE, dwCycle :=1);
		fbTimeFrederik						:FB_LocalSystemTime:= (bEnable 	:= TRUE, dwCycle :=1);


		EStopStatus				AT%I*	:	DWORD;
		EStopReset				AT%Q*	:	DWORD;
		PEstopReset				AT%Q*	:	DWORD;
		EStopTwinSAFE			AT%I*	:	BOOL:=TRUE;
		EStoped							:	BOOL:=FALSE;
		EStopedOld						:	BOOL:=FALSE;

		PeriodicSelfCheck		AT%Q*	:	BOOL:=FALSE;
		SPS0Sperre				AT%Q*	:	BOOL:=TRUE;
		ReSync							:	REAL:=0.0;

(*--------------------------*)
		UPMessage						:	STRING(650);
		DownMessage1					:	STRING(600);


	nErrId: BOOL;
	Daten: STRING;		(*Datenstring*)

	sPosWinUI: STRING;
	sVelWinUI: STRING;
	sAccTotUI: STRING;
	sGuidePosManualMaxUI: STRING;

	GUINotHaltIN					:	INT 		:=0;
	GUINotHaltOUT	AT%Q*		:	BOOL	:=FALSE;
	PGUINotHaltOUT	AT%Q*		:	BOOL	:=FALSE;

END_VAR
;>IF bCloseAll THEN (*On PLC reset or program download close all old connections *)
	bCloseAll := FALSE;
	fbSocketCloseAll( sSrvNetId:= g_sTcIpConnSvrAddr, bExecute:= TRUE, tTimeout:= T#10s );
ELSE
	fbSocketCloseAll( bExecute:= FALSE );
END_IF
IF fbSocketCloseAll.bError THEN
	LogError( 'FB_SocketCloseALL (UDP)', fbSocketCloseAll.nErrId );
				nErrIdA := fbSocketCloseAll.nErrId;
END_IF

IF NOT fbSocketCloseAll.bBusy AND NOT fbSocketCloseAll.bError THEN
	fbPeerToPeer1( sendFifo := sendFifo1, receiveFifo := receiveFifo1, sLocalHost := LOCAL_HOST_IP, nLocalPort := LOCAL_HOST_PORT1, bEnable := TRUE );
	(* Try Second Socket End*)

	REPEAT
		receiveFifo1.RemoveHead( old => entryReceivedFrom1 );
		IF receiveFifo1.bOk THEN
			DownMessage1 := '';
			iDownDaten:=0;
			PtDaten := ADR(entryReceivedFrom1.msg);
			WHILE iDownDaten < SIZEOF(entryReceivedFrom1.msg) AND PtDaten^ <> 0 DO
				DownMessage1:=CONCAT(DownMessage1,CHR(PtDaten^));
				iDownDaten:=iDownDaten+1;
				PtDaten := ADR(entryReceivedFrom1.msg)+iDownDaten;
			END_WHILE
			LifetickUIrx := STRING_TO_WORD(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			LifetickDiff1 := LifetickUItx-LifetickUIrx;
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			Modus       := (LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			OwnPID := (LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			IF Intent = 'True' THEN
				ControlPID := OwnPID;
			END_IF
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			ControlPIDTx 	:= STRING_TO_UINT(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			Intent := (LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			ControlIN 		:= STRING_TO_UINT(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			PControlIN		:= ControlIN;
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			GuideControlUI:= STRING_TO_UINT(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			GuideControl := GuideControlUI;
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			SpeedSollIN:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));(*auf UI Seite SpeedSoll*)
			PSpeedSollIN	:= SpeedSollIN;
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			GuideSollSpeedUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			PGuideSollSpeedUI := GuideSollSpeedUI;
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			PosSoll:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			PPosSoll:=PosSoll;
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			EStopReset:= STRING_TO_DWORD(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			PEStopReset:= EStopReset;
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			ReSync := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
			GUINotHaltIN := STRING_TO_INT(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
			IF Modus = 'w' THEN
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));(*auf UI Seite AccMax*)
				AccIN       := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PAccIn := AccIN;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));(*auf UI Seite AccMax*)
				DccIN       := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PDccIN :=DccIn;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				PosMaxHardUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PPosMaxHardUI:=PosMaxHardUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				PosMaxUserUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PPosMaxUserUI:=PosMaxUserUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				PosMinUserUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PPosMinUserUI:=PosMinUserUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				PosMinHardUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PPosMinHardUI:=PosMinHardUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				SpeedMaxUI  := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PSpeedMaxUI := SpeedMaxUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				AccMaxUI    := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PAccMaxUI	:= AccMaxUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				DccMaxUI    := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PDccMaxUI	:= DccMaxUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				AmpMaxUI    := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PAmpMaxUI	:= AmpMaxUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				FilterP  	:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PFilterP	:= FilterP;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				FilterI  	:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PFilterI	:= FilterI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				FilterD     := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PFilterD	:= FilterD;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				FilterIL    := STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PFilterIL	:= FilterIL;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				GuidePitchUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PGuidePitchUI:=GuidePitchUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				GuidePosMaxUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PGuidePosMaxUI:=GuidePosMaxUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				GuidePosMinUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PGuidePosMinUI:= GuidePosMinUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				VelOrPos:= (LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				PosWinUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PPosWinUI:=PosWinUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				VelWinUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PVelWinUI:= VelWinUI;
				DownMessage1 := RIGHT(DownMessage1,LEN(DownMessage1)-FIND(DownMessage1,';'));
				AccTotUI:= STRING_TO_REAL(LEFT(DownMessage1,FIND(DownMessage1,';')-1));
				PAccTotUI:=AccTotUI;
			END_IF
		END_IF
	UNTIL NOT receiveFifo1.bOk
	END_REPEAT


	UpMessage:= '';
	UpMessage:= CONCAT(UpMessage,OwnPID); (*FAKE Controling PID *)			(*0  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,REAL_TO_STRING (LifetickUItx));			(*1  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,WORD_TO_STRING (Status));					(*2  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,WORD_TO_STRING (GuideStatus)); 			(*3  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (PosIst,5,TRUE)); 					(*4  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (SpeedIstUI,5,TRUE)); 				(*5  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (MasterMomentUI,5,TRUE)); 	(*6  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (CabTemperatureUI,1,TRUE));(*7  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,Name);										(*8  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (GearToUI,3,TRUE)); 		(*9  *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR(PosMaxHardUI,3,TRUE)); 			(*10 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (PosMaxUserUI,3,TRUE)); 	(*11 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (PosMinUserUI,3,TRUE)); 	(*12 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (PosMinHardUI,3,TRUE)); 	(*13 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (SpeedMaxUI,2,TRUE)); 		(*14 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (AccMaxUI,2,TRUE)); 		(*15 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (DccMaxUI,2,TRUE)); 		(*16 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (AmpMaxUI,2,TRUE)); 		(*17 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (FilterP,6,TRUE)); 		(*18 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (FilterI,6,TRUE)); 		(*19 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (FilterD,6,TRUE)); 		(*20 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (FilterIL,6,TRUE)); 		(*21 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (RopeSWLL,1,TRUE)); 		(*22 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (RopeDiameter,1,TRUE)); 	(*23 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,RopeType); 								(*24 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,RopeNumber); 								(*25 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (RopeLength,2,TRUE)); 		(*26 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (GuidePitchUI,1,TRUE)); 	(*27 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (GuidePosMaxUI,4,TRUE)); 	(*28 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (GuidePosMinUI,4,TRUE)); 	(*29 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (GuidePosIstUI,4,TRUE));		 	(*30 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (GuideIstSpeedUI,2,TRUE));			(*31 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (MotAuslastUI,1,TRUE));	(*32 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (ActCurUI,1,TRUE));		(*33 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (SpeedMaxforUI,2,TRUE));	(*34 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,LREAL_TO_FMTSTR (PosDiffForUI,5,TRUE));	(*35 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,DWORD_TO_STRING (RampenformUI));			(*36 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,DWORD_TO_STRING (EStopStatus));			(*37 *)
	UpMessage:= CONCAT(UpMessage,';');
	UpMessage:= CONCAT(UpMessage,'EOD\');
	UpMessage:= CONCAT(UpMessage,';');

	StrOffset:=0;
	iDatenArray:=0;
	PtDaten := ADR(UpMessage);
	WHILE (PtDaten^<>92 AND PtDaten^<> 0) DO
		PtDaten := ADR(UpMessage)+StrOffset;
		StrOffset := StrOffset + 1;
		DatenArray[iDatenArray]:= PtDaten^;
		iDatenArray:=iDatenArray+1;
	END_WHILE
	DatenArray[iDatenArray]:= 59;
	iDatenArray:=iDatenArray+1;

	IF EStopTwinSAFE AND ReSync = 1 THEN
		EStoped := FALSE;
	END_IF
	IF NOT EStopTwinSAFE THEN
		EStoped := TRUE;
	END_IF

	fbTime();
	fbTimeFrederik(sNetID:= AmsIDFrederik);

	IF EStopTwinSAFE AND NOT EStoped THEN
		IF fbTimeFrederik.bValid THEN
			SystemTime :='N_';
			SystemTime :=CONCAT(SystemTime,SYSTEMTIME_TO_STRING( fbTimeFrederik.systemTime )) ;
		ELSE
			SystemTime :='L_';
			SystemTime :=CONCAT(SystemTime,SYSTEMTIME_TO_STRING(fbTime.systemTime ));
		END_IF
		sCutPos := LREAL_TO_FMTSTR (PosIst,5,TRUE);
		sCutVel := LREAL_TO_FMTSTR (SpeedIstUI,5,TRUE);
	END_IF

	StrOffset:=0;
	PtDaten := ADR(SystemTime);
	WHILE (StrOffset  < LEN(SystemTime)+1) DO
		PtDaten := ADR(SystemTime)+StrOffset;
		StrOffset := StrOffset + 1;
		DatenArray[iDatenArray]:= PtDaten^;
		iDatenArray:=iDatenArray+1;
	END_WHILE
	DatenArray[iDatenArray-1]:= 59;

	StrOffset:=0;
	PtDaten := ADR(sCutPos);
	WHILE (StrOffset < LEN(sCutPos) AND PtDaten^ <> 0) DO
		PtDaten := ADR(sCutPos)+StrOffset;
		StrOffset := StrOffset + 1;
		DatenArray[iDatenArray]:= PtDaten^;
		iDatenArray:=iDatenArray+1;
	END_WHILE
	DatenArray[iDatenArray-1]:= 59;


	StrOffset:=0;
	PtDaten := ADR(sCutVel);
	WHILE (StrOffset < LEN(sCutVel) AND PtDaten^ <> 0) DO
		PtDaten := ADR(sCutVel)+StrOffset;
		StrOffset := StrOffset + 1;
		DatenArray[iDatenArray]:= PtDaten^;
		iDatenArray:=iDatenArray+1;
	END_WHILE
	DatenArray[iDatenArray-1]:= 59;

	sPosWinUI := LREAL_TO_FMTSTR (PosWinUI,5,TRUE);
	sVelWinUI := LREAL_TO_FMTSTR (VelWinUI,5,TRUE);
	sAccTotUI := LREAL_TO_FMTSTR (AccTotUI,3,TRUE);
	sGuidePosManualMaxUI := LREAL_TO_FMTSTR (GuidePosManualMaxUI,3,TRUE);

	StrOffset:=0;
	PtDaten := ADR(sPosWinUI);
	WHILE (StrOffset < LEN(sPosWinUI) AND PtDaten^ <> 0) DO
		PtDaten := ADR(sPosWinUI)+StrOffset;
		StrOffset := StrOffset + 1;
		DatenArray[iDatenArray]:= PtDaten^;
		iDatenArray:=iDatenArray+1;
	END_WHILE
	DatenArray[iDatenArray-1]:= 59;

	StrOffset:=0;
	PtDaten := ADR(sVelWinUI);
	WHILE (StrOffset < LEN(sVelWinUI) AND PtDaten^ <> 0) DO
		PtDaten := ADR(sVelWinUI)+StrOffset;
		StrOffset := StrOffset + 1;
		DatenArray[iDatenArray]:= PtDaten^;
		iDatenArray:=iDatenArray+1;
	END_WHILE
	DatenArray[iDatenArray-1]:= 59;

	StrOffset:=0;
	PtDaten := ADR(sAccTotUI);
	WHILE (StrOffset < LEN(sAccTotUI) AND PtDaten^ <> 0) DO
		PtDaten := ADR(sAccTotUI)+StrOffset;
		StrOffset := StrOffset + 1;
		DatenArray[iDatenArray]:= PtDaten^;
		iDatenArray:=iDatenArray+1;
	END_WHILE
	DatenArray[iDatenArray-1]:= 59;

	StrOffset:=0;
	PtDaten := ADR(sGuidePosManualMaxUI);
	WHILE (StrOffset < LEN(sGuidePosManualMaxUI) AND PtDaten^ <> 0) DO
		PtDaten := ADR(sGuidePosManualMaxUI)+StrOffset;
		StrOffset := StrOffset + 1;
		DatenArray[iDatenArray]:= PtDaten^;
		iDatenArray:=iDatenArray+1;
	END_WHILE
	DatenArray[iDatenArray-1]:= 59;


	sendToEntry1.nRemotePort 		:= REMOTE_HOST_PORT1;			(* remote host port number*)
	sendToEntry1.sRemoteHost 		:= REMOTE_HOST_IP;				(* remote host IP address *)
	sendToEntry1.msg				:= DatenArray;
	IF sendFifo1.nCount < 4 THEN
		sendFifo1.AddTail( new := sendToEntry1 );
		IF NOT sendFifo1.bOk THEN												(* check for fifo overflow*)
			LogError( 'Send fifo1 overflow!', PLCPRJ_ERROR_SENDFIFO_OVERFLOW );
		END_IF
	END_IF
END_IF
IF PeriodicSelfCheck = TRUE THEN
	PeriodicSelfCheck := FALSE;
ELSE
	PeriodicSelfCheck := TRUE;
END_IF
IF Modus = 'E' THEN
	SPS0Sperre := FALSE;
ELSE
	SPS0Sperre := TRUE;
END_IF
IF LifetickDiff > 500 THEN
	OwnPID := '0000';
	ControlPID := '0000';
	Intent := 'False';
END_IF

IF GUINotHaltIN = 1 THEN
	GUINotHaltOUT :=TRUE;
	PGUINotHaltOUT := TRUE;
END_IF

VAR_INPUT
	sc		: UDINT;
END_VAR


J"TcSystem.lib 1.7.11 10:22:02@
N TcpIp.lib 29.5.06 14:26:36@|zD&TcUtilities.lib 31.8.11 18:09:14@\^N#ChrAscBX.lbx 11.3.04 11:02:42@2+P@CONCAT@	CTD@	CTU@
CTUD@
DELETE@
F_TRIG@
FIND@
INSERT@
LEFT@	LEN@	MID@
R_TRIG@
REPLACE@
RIGHT@RS@
SEMA@SR@	TOF@	TON@TP@Global Variables 0@
zFW_AdsClearEvents@
FW_NoOfByteFW_SystemInfoTypeFW_SystemTaskInfoType
FW_TcEventFW_AdsLogDINT@FW_AdsLogEvent@FW_AdsLogLREAL@FW_AdsLogSTR@FW_AdsRdWrt@FW_AdsRdWrtInd@FW_AdsRdWrtRes@FW_AdsRead@FW_AdsReadDeviceInfo@FW_AdsReadInd@FW_AdsReadRes@FW_AdsReadState@FW_AdsWrite@FW_AdsWriteControl@FW_AdsWriteInd@FW_AdsWriteRes@FW_DRand@FW_GetCpuAccount@FW_GetCpuCounter@FW_GetCurTaskIndex@FW_GetSystemTime@FW_GetVersionTcBase@FW_LptSignal@FW_MemCmp@FW_MemCpy@FW_MemMove@FW_MemSet@FW_PortRead@FW_PortWrite@PQADSCLEAREVENTS@E_IOAccessSize
E_OpenPath
E_SeekOriginE_TcEventClassE_TcEventClearModesE_TcEventPriorityE_TcEventStreamTypeExpressionResult
SFCActionType
SFCStepTypeST_AdsBaDevApiHeadST_AdsBaDevApiIoCtlModifierST_AdsBaDevApiReq
ST_AmsAddr
ST_StructMemberAlignmentProbeSYSTEMINFOTYPESYSTEMTASKINFOTYPE
T_AmsNetId
T_AmsNetIdArr	T_AmsPort
T_IPv4Addr
T_IPv4AddrArr
T_MaxStringT_U64KAFFINITYTcEventADSLOGDINT@ADSLOGEVENT@ADSLOGLREAL@ADSLOGSTR@ADSRDDEVINFO@ADSRDSTATE@ADSRDWRT@ADSRDWRTEX@ADSRDWRTIND@ADSRDWRTRES@
ADSREAD@ADSREADEX@ADSREADIND@ADSREADRES@ADSWRITE@ADSWRITEIND@ADSWRITERES@ADSWRTCTL@AnalyzeExpression@AnalyzeExpressionCombined@
AnalyzeExpressionTable@AppendErrorString@BAVERSION_TO_DWORD@CLEARBIT32@CSETBIT32@
DRAND@F_CompareFwVersion@F_CreateAmsNetId@F_CreateIPv4Addr@ F_GetStructMemberAlignment@F_GetVersionTcSystem@F_IOPortRead@F_IOPortWrite@F_ScanAmsNetIds@F_ScanIPv4AddrIds@F_SplitPathName@
F_ToASC@
F_ToCHR@FB_BaDeviceIoControl@FB_BaGenGetVersion@FB_CreateDir@
FB_EOF@FB_FileClose@FB_FileDelete@FB_FileGets@FB_FileOpen@FB_FilePuts@FB_FileRead@FB_FileRename@FB_FileSeek@FB_FileTell@FB_FileWrite@FB_PcWatchdog@FB_RemoveDir@FB_SimpleAdsLogEvent@FILECLOSE@FILEOPEN@FILEREAD@FILESEEK@FILEWRITE@FW_CallGenericFb@FW_CallGenericFun@GETBIT32@GETCPUACCOUNT@GETCPUCOUNTER@GETCURTASKINDEX@GETSYSTEMTIME@GETTASKTIME@LPTSIGNAL@
MEMCMP@
MEMCPY@
MEMMOVE@
MEMSET@
ROL32@
ROR32@SETBIT32@SFCActionControl@
SHL32@
SHR32@pGlobal_Variables@SYSTEMSERVICE_FRENAME"ADSIGRP_IOIMAGE_RWOB"SYSTEMSERVICE_CHANGENETID"FOPEN_MODEREAD"SYSTEMSERVICE_CLOSEHANDLE"SYSTEMSERVICE_FTELL"
BOOTDATAFLAGS_RETAIN_REQUESTED"ADSSTATE_RESET"SYSTEMSERVICE_FGETS"SYSTEMSERVICE_FEOF"AMSPORT_R0_CAMTOOL"PI"SYSTEMSERVICE_FSEEK"ADSSTATE_RECONFIG"FILE_OPENCREATE"ADSIGRP_SYMNAME"ADSSTATE_START"ADSSTATE_LOADCFG"
ADSSTATE_IDLE"BOOTDATAFLAGS_RETAIN_LOADED"
FILE_SEEKEND"ADSIGRP_SYM_HNDBYNAME"TCEVENTFLAG_FMTSELF"ADSIGRP_SYMNOTE"SYSTEMSERVICE_FWRITE""SYSTEMSERVICE_REG_HKEYLOCALMACHINE"ADSLOG_MSGTYPE_STRING"TCEVENT_FMTPRGSIZE"ADSIGRP_SYM_VERSION"ADSIGRP_IOIMAGE_RWIOB"ADSIGRP_IOIMAGE_ROSIZE"ADSIGRP_SYM_INFOBYNAMEEX"ADSIGRP_IOIMAGE_RISIZE"AMSPORT_R0_NCSAF"TCEVENTSTATE_INVALID"TCEVENTSTATE_CONFIRMED"
FILE_OPENREAD"AMSPORT_LOGGER"BOOTDATAFLAGS_PERSISTENT_LOADED"TCEVENTSTATE_RESETCON"SYSTEMSERVICE_FDELETE"	FILE_READ"MAX_STRING_LENGTH"ADSSTATE_SHUTDOWN"AMSPORT_R0_CAM"ADSIGRP_SYMVAL"ADSIGRP_IOIMAGE_RWIX"ADSIGRP_SYM_DOWNLOAD"ADSIGRP_SYM_UPLOAD"TIMESERVICE_RTCTIMEDIFF"
AMSPORT_R0_NC"ADSIGRP_IOIMAGE_RWIB"SYSTEMSTATEFLAGS_BSOD"AMSPORT_R0_CNC"
BOOTDATAFLAGS_RETAIN_INVALID"ADSIOFFS_DEVDATA_ADSSTATE"ADSSTATE_SAVECFG"SYSTEMSERVICE_OPENWRITE"SYSTEMSERVICE_FCLOSE"ADSSTATE_CONFIG"ADSSTATE_POWERGOOD"ADSIGRP_SYM_INFOBYNAME"SYSTEMSERVICE_FSCANF"ADSIGRP_SYM_UPLOADINFO"SYSTEMSERVICE_OPENREAD"SYSTEMSERVICE_RMDIR"TIMESERVICE_ADJUSTTIMETORTC"TCEVENTFLAG_SRCID"SYSTEMSERVICE_FPUTS"FOPEN_MODEAPPEND"ADSLOG_MSGTYPE_MSGBOX"ADSSTATE_SUSPEND"
FILE_WRITE"SYSTEMSERVICE_SENDEMAIL"
SYSTEMSTATEFLAGS_RTVIOLATION"AMSPORT_R0_ISG"AMSPORT_R0_PLC_RTS4"TIMESERVICE_DATEANDTIME"AMSPORT_R0_PLC_RTS3"TCEVENTFLAG_AUTOFMTALL"AMSPORT_R0_PLC_RTS2"AMSPORT_R0_PLC_RTS1"TCEVENTFLAG_MSGBOX"FILE_OPENWRITE" BOOTDATAFLAGS_PERSISTENT_INVALID"
ADSSTATE_RUN"ADSSTATE_POWERFAILURE"ADSLOG_MSGTYPE_ERROR"FOPEN_MODEWRITE"ADSLOG_MSGTYPE_WARN"AMSPORT_EVENTLOG"AMSPORT_R3_SCOPESERVER"SYSTEMSERVICE_STARTPROCESS"ADSLOG_MSGTYPE_LOG"ADSLOG_MSGTYPE_HINT"FOPEN_MODEPLUS"AMSPORT_R0_NCSVB"TCEVENTFLAG_LOG"SYSTEMSERVICE_MKDIR"ADSLOG_MSGTYPE_RESOURCE"TIMESERVICE_SYSTEMTIMES"ADSIGRP_IOIMAGE_CLEARI"AMSPORT_R0_LINE"ADSIGRP_IOIMAGE_CLEARO"FOPEN_MODETEXT"SYSTEMSERVICE_FPRINTF"ADSSTATE_RESUME"TCEVENTSTATE_RESET"
AMSPORT_R0_IO"TCEVENTFLAG_PRIOCLASS"ADSSTATE_INVALID"DEFAULT_ADS_TIMEOUT"ADSIGRP_SYM_VALBYNAME"TCEVENTSTATE_SIGNALED"ADSIGRP_DEVICE_DATA"ADSSTATE_ERROR"AMSPORT_R0_RTIME"ADSIGRP_SYM_RELEASEHND"
TIMESERVICE_TIMEZONINFORMATION"SYSTEMSERVICE_CREATEFILE"TCEVENT_SRCNAMESIZE"
ADSSTATE_INIT"SYSTEMSERVICE_FREAD"ADSIGRP_SYMTAB"SYSTEMSERVICE_TIMESERVICES"
ADSSTATE_STOP"FILE_SEEKBEGIN"ADSSTATE_MAXSTATES"SYSTEMSERVICE_OPENCREATE"SYSTEMSERVICE_FOPEN"AMSPORT_R3_SYSSERV"ADSIOFFS_DEVDATA_DEVSTATE"FOPEN_MODEBINARY"AMSPORT_R0_PLC"ADSIGRP_SYM_VALBYHND"ADSIGRP_IOIMAGE_RWOX"
F_GetVersionTcpIp@E_WinsockError
ST_SockAddrST_TcIpConnSvrResponseST_TcIpConnSvrUdpBuffer	T_HSOCKETFB_SocketAccept@FB_SocketClose@FB_SocketCloseAll@FB_SocketConnect@FB_SocketListen@FB_SocketReceive@FB_SocketSend@FB_SocketUdpCreate@
FB_SocketUdpReceiveFrom@FB_SocketUdpSendTo@Global_Variables@TCPADSCONLST_IOF_ACCEPT TCPADS_IGR_SENDBYHDL TCPADSCONLST_IOF_UDPBIND AMSPORT_TCPIPSRV TCPADS_IGR_RECVFROMBYHDL TCPADSCONLST_IOF_CLOSEALL TCPADS_MAXUDP_BUFFSIZE TCPADS_NULL_HSOCKET TCPADSCONLST_IOF_CONNECT TCPADS_IGR_RECVBYHDL TCPADS_IGR_SENDTOBYHDL TCPADS_IGR_PEERBYHDL TCPADSCONLST_IOF_LISTEN TCPADS_IGR_CLOSEBYHDL TCPADS_IGR_CONLIST (ßARG_TO_CSVFIELD@>
ADSDATATYPEIDE_AmsLoggerMode	E_ArgType
E_DbgContextE_DbgDirection
E_EnumCmdTypeE_FileRBufferCmdE_HashPrefixTypes
E_MIB_IF_TypeE_NumGroupTypesE_PersistentModeE_PrefixFlagParamE_RegValueTypeE_RouteTransportType
E_SBCSTypeE_ScopeServerState
E_TimeZoneIDE_TypeFieldParamE_UTILITIES_ERRORCODESOTSTRUCTPROFILERSTRUCTREMOTEPCREMOTEPCINFOSTRUCTROUTERINFOSTRUCT
ST_AmsGetTimeZoneInformationST_AmsLoggerReqST_AmsRouteEntryST_AmsRouteEntryHeadST_AmsRouteSystemEntryST_DeviceIdentificationST_DeviceIdentificationExST_FileAttributesST_FileRBufferHeadST_FindFileEntryST_FindFileSystemEntryST_FormatParametersST_HKeySrvReadST_HKeySrvWriteST_IP_ADAPTER_INFOST_IP_ADDR_STRINGST_IPAdapterHwAddrST_IPAdapterInfo
ST_SBCSTable#ST_ScopeServerRecordModeDescriptionST_TcRouterStatusInfoST_TimeZoneInformationSTARTPROC_BUFFERSYMINFO_BUFFER
SYMINFOSTRUCTT_Arg
T_FILETIMET_FIX16
T_FloatRecT_HashTableEntry
T_HHASHTABLE
T_HLINKEDLISTT_HUGE_INTEGERT_LARGE_INTEGERT_LinkedListEntryT_UHUGE_INTEGERT_ULARGE_INTEGER
TIMESTRUCTBCD_TO_DEC@BE128_TO_HOST@BE16_TO_HOST@BE32_TO_HOST@BE64_TO_HOST@BYTEARR_TO_MAXSTRING@CSVFIELD_TO_ARG@CSVFIELD_TO_STRING@DATA_TO_HEXSTR@DCF77_TIME@DCF77_TIME_EX@DEC_TO_BCD@DEG_TO_RAD@DINT_TO_DECSTR@DT_TO_FILETIME@DT_TO_SYSTEMTIME@DWORD_TO_BINSTR@DWORD_TO_DECSTR@DWORD_TO_HEXSTR@DWORD_TO_LREALEX@DWORD_TO_OCTSTR@F_ARGCMP@F_ARGCPY@F_ARGIsZero@F_BIGTYPE@
F_BOOL@
F_BYTE@F_BYTE_TO_CRC16_CCITT@F_CheckSum16@F_CRC16_CCITT@F_CreateHashTableHnd@F_CreateLinkedListHnd@F_DATA_TO_CRC16_CCITT@
F_DINT@
F_DWORD@F_FormatArgToStr@F_GetDayOfMonthEx@F_GetDayOfWeek@
F_GetDOYOfYearMonthDay@F_GetFloatRec@F_GetMaxMonthDays@F_GetMonthOfDOY@
F_GetVersionTcUtilities@F_GetWeekOfTheYear@
F_HUGE@
F_INT@
F_LARGE@
F_LREAL@
F_LTrim@
F_REAL@
F_RTrim@
F_SINT@F_STRING@F_SwapReal@F_SwapRealEx@F_ToLCase@F_ToUCase@
F_TranslateFileTimeBias@
F_UDINT@
F_UHUGE@
F_UINT@F_ULARGE@
F_USINT@
F_WORD@F_YearIsLeapYear@FB_AddRouteEntry@FB_AmsLogger@FB_BasicPID@FB_BufferedTextFileWriter@'FB_BufferedTextFileWriter.A_Reset@FB_ConnectScopeServer@FB_CSVMemBufferReader@FB_CSVMemBufferWriter@FB_DbgOutputCtrl@
FB_DbgOutputCtrl.A_Log@FB_DbgOutputCtrl.A_LogHex@
FB_DbgOutputCtrl.A_Reset@
FB_DisconnectScopeServer@FB_EnumFindFileEntry@FB_EnumFindFileList@FB_EnumRouteEntry@FB_EnumStringNumbers@FB_FileRingBuffer@!FB_FileRingBuffer.A_AddTail@FB_FileRingBuffer.A_Close@ FB_FileRingBuffer.A_Create@!FB_FileRingBuffer.A_GetHead@
FB_FileRingBuffer.A_Open@$FB_FileRingBuffer.A_RemoveHead@FB_FileRingBuffer.A_Reset@&FB_FileTimeToTzSpecificLocalTime@.FB_FileTimeToTzSpecificLocalTime.A_Reset@FB_FormatString@FB_GetAdaptersInfo@ FB_GetDeviceIdentification@"FB_GetDeviceIdentificationEx@FB_GetHostAddrByName@FB_GetHostName@FB_GetLocalAmsNetId@
FB_GetRouterStatusInfo@FB_GetTimeZoneInformation@FB_HashTableCtrl@
FB_HashTableCtrl.A_Add@!FB_HashTableCtrl.A_GetFirst@)FB_HashTableCtrl.A_GetIndexAtPosPtr@ FB_HashTableCtrl.A_GetNext@FB_HashTableCtrl.A_Lookup@FB_HashTableCtrl.A_Remove@"FB_HashTableCtrl.A_RemoveAll@$FB_HashTableCtrl.A_RemoveFirst@
FB_HashTableCtrl.A_Reset@FB_LinkedListCtrl@&FB_LinkedListCtrl.A_AddHeadValue@&FB_LinkedListCtrl.A_AddTailValue@"FB_LinkedListCtrl.A_FindNext@"FB_LinkedListCtrl.A_FindPrev@!FB_LinkedListCtrl.A_GetHead@*FB_LinkedListCtrl.A_GetIndexAtPosPtr@!FB_LinkedListCtrl.A_GetNext@!FB_LinkedListCtrl.A_GetPrev@!FB_LinkedListCtrl.A_GetTail@)FB_LinkedListCtrl.A_RemoveHeadValue@)FB_LinkedListCtrl.A_RemoveTailValue@-FB_LinkedListCtrl.A_RemoveValueAtPosPtr@FB_LinkedListCtrl.A_Reset@*FB_LinkedListCtrl.A_SetValueAtPosPtr@FB_LocalSystemTime@FB_MemBufferMerge@FB_MemBufferSplit@FB_MemRingBuffer@ FB_MemRingBuffer.A_AddTail@ FB_MemRingBuffer.A_GetHead@#FB_MemRingBuffer.A_RemoveHead@
FB_MemRingBuffer.A_Reset@FB_MemRingBufferEx@"FB_MemRingBufferEx.A_AddTail@#FB_MemRingBufferEx.A_FreeHead@&FB_MemRingBufferEx.A_GetFreeSize@"FB_MemRingBufferEx.A_GetHead@ FB_MemRingBufferEx.A_Reset@FB_RegQueryValue@FB_RegSetValue@FB_RemoveRouteEntry@ FB_ResetScopeServerControl@
FB_SaveScopeServerData@FB_ScopeServerControl@FB_SetTimeZoneInformation@FB_StartScopeServer@FB_StopScopeServer@FB_StringRingBuffer@#FB_StringRingBuffer.A_AddTail@#FB_StringRingBuffer.A_GetHead@&FB_StringRingBuffer.A_RemoveHead@!FB_StringRingBuffer.A_Reset@(FB_SystemTimeToTzSpecificLocalTime@0FB_SystemTimeToTzSpecificLocalTime.A_Reset@FB_TextFileRingBuffer@%FB_TextFileRingBuffer.A_AddTail@#FB_TextFileRingBuffer.A_Close@"FB_TextFileRingBuffer.A_Open@#FB_TextFileRingBuffer.A_Reset@"FB_TranslateFileTimeToZoneID@*FB_TranslateFileTimeToZoneID.A_Reset@&FB_TzSpecificLocalTimeToFileTime@.FB_TzSpecificLocalTimeToFileTime.A_Reset@(FB_TzSpecificLocalTimeToSystemTime@0FB_TzSpecificLocalTimeToSystemTime.A_Reset@
FB_WritePersistentData@FILETIME_TO_DT@
FILETIME_TO_SYSTEMTIME@FIX16_TO_LREAL@FIX16_TO_WORD@FIX16Add@FIX16Align@FIX16Div@FIX16Mul@FIX16Sub@GetRemotePCInfo@HEXSTR_TO_DATA@HOST_TO_BE128@HOST_TO_BE16@HOST_TO_BE32@HOST_TO_BE64@INT64_TO_LREAL@Int64Add64@Int64Add64Ex@Int64Cmp64@Int64Div64Ex@Int64IsZero@Int64Negate@Int64Not@Int64Sub64@IsFinite@LARGE_INTEGER@LARGE_TO_ULARGE@LREAL_TO_FIX16@LREAL_TO_FMTSTR@LREAL_TO_INT64@LREAL_TO_UINT64@MAXSTRING_TO_BYTEARR@NT_AbortShutdown@NT_GetTime@NT_Reboot@NT_SetLocalTime@NT_SetTimeToRTCTime@NT_Shutdown@NT_StartProcess@OTSTRUCT_TO_TIME@PBOOL_TO_BOOL@PBYTE_TO_BYTE@PDATE_TO_DATE@PDINT_TO_DINT@PDT_TO_DT@PDWORD_TO_DWORD@PHUGE_TO_HUGE@PINT_TO_INT@PLARGE_TO_LARGE@PLC_ReadSymInfo@PLC_ReadSymInfoByName@
PLC_ReadSymInfoByNameEx@PLC_Reset@PLC_Start@PLC_Stop@PLREAL_TO_LREAL@
PMAXSTRING_TO_MAXSTRING@PREAL_TO_REAL@Profiler@PSINT_TO_SINT@PSTRING_TO_STRING@PTIME_TO_TIME@PTOD_TO_TOD@PUDINT_TO_UDINT@PUHUGE_TO_UHUGE@PUINT64_TO_UINT64@PUINT_TO_UINT@PULARGE_TO_ULARGE@PUSINT_TO_USINT@PWORD_TO_WORD@RAD_TO_DEG@
ROUTETRANSPORT_TO_STRING@	RTC@
RTC_EX@
RTC_EX2@ScopeASCIIExport@ScopeExit@ScopeGetRecordLen@ScopeGetState@ScopeLoadFile@ScopeManualTrigger@ScopeSaveAs@ScopeSetOffline@ScopeSetOnline@ScopeSetRecordLen@ScopeViewExport@STRING_TO_CSVFIELD@STRING_TO_SYSTEMTIME@STRING_TO_UINT64@SYSTEMTIME_TO_DT@
SYSTEMTIME_TO_FILETIME@SYSTEMTIME_TO_STRING@TC_Config@TC_CpuUsage@TC_Restart@
