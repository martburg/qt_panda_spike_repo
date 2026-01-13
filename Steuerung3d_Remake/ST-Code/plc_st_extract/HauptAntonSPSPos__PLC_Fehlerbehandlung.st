PROGRAM PLC_Fehlerbehandlung

VAR

	Input	        		AT%I*	:	DINT;	(* Master Klemmen *)
	StatusMaster			AT%I*	:	UINT;	(* Statuswort     *)
	StatusSlave				AT%I*	:	UINT;	(* Statuswort     *)

	StatusBit0				AT%I*	:	BOOL;	(* Group 3 FB                             *)
	StatusBit1				AT%I*	:	BOOL;	(* Group 3 COM                            *)
	StatusBit2				AT%I*	:	BOOL;	(* Group 3 OUT                            *)
	StatusBit3				AT%I*	:	BOOL;	(* Group 2 FB                             *)
	StatusBit4				AT%I*	:	BOOL;	(* Group 2 COM                            *)
	StatusBit5				AT%I*	:	BOOL;	(* Group 2 OUT                            *)
	StatusBit6				AT%I*	:	BOOL;	(* Group 1 FB                             *)
	StatusBit7				AT%I*	:	BOOL;	(* Group 1 COM                            *)
	StatusBit8				AT%I*	:	BOOL;	(* Group 1 OUT                            *)
	StatusBit9				AT%I*	:	BOOL;	(* FB 49         E-Stop Master            *)
	StatusBit10				AT%I*	:	BOOL;	(* FB 50          E-Stop Slave            *)
	StatusBit11				AT%I*	:	BOOL;	(* FB 56          E-Stop All              *)
	StatusBit12				AT%I*	:	BOOL;	(* FB 57          Freigabe                *)
	StatusBit13				AT%I*	:	BOOL;	(* Term 3    CH 3 E-Stop Schrank          *)
	StatusBit14				AT%I*	:	BOOL;	(* Term 5    CH 2 E-Stop Flache           *)
	StatusBit15				AT%I*	:	BOOL;	(* FB 11          Steuerwort              *)
	StatusBit16				AT%I*	:	BOOL;	(* Term 3    CH 2 Betriebsbereit 30kW     *)
	StatusBit17				AT%I*	:	BOOL;	(* Term 3    CH 4 Betriebsbereit 05kW     *)
	StatusBit18				AT%I*	:	BOOL;	(* Klemme 18 CH 1 Bremswaechter1          *)
	StatusBit19				AT%I*	:	BOOL;	(* Klemme 18 CH 2 Bremswaechter2          *)
	StatusBit20				AT%I*	:	BOOL;	(* FB 29          Encoder Plausibilität   *)
	StatusBit21				AT%I*	:	BOOL;	(* FB 44          SPS0 SelfCheck          *)
	StatusBit22				AT%I*	:	BOOL;	(* FB 45          SPS1 SelfCheck          *)
	StatusBit23				AT%I*	:	BOOL;	(* FB 46          SPS2 SelfCheck          *)
	StatusBit24				AT%I*	:	BOOL;   (* FB 30          SynchronPos             *)
	StatusBit25				AT%I*	:	BOOL;	(* FB 31          SynchronVel             *)
	StatusBit26				AT%I*	:	BOOL;	(* FB 32          Endlage                 *)
	StatusBit27				AT%I*	:	BOOL;	(* FB 53          Taster                  *)
	StatusBit28				AT%I*	:	BOOL;	(* Klemme 19 CH 3 Schuetz 1,2             *)
	StatusBit29				AT%I*	:	BOOL;	(* Klemme 19 CH 4 Schuetz 3               *)
	StatusBit30				AT%I*	:	BOOL;   (* Term 5    CH 3 Schalter Rechts         *)
	StatusBit31				AT%I*	:	BOOL;   (* Term 5    CH 1 Schalter Links          *)

	EStopStatus					AT%Q*	:	DWORD:=0;
	EStopReset					AT%I*	:	DWORD;
	Error_Ack					AT%Q*	:	BOOL;
	Restart						AT%Q*  	:	BOOL;
	ResetMaster					AT%Q*	:	UINT;	(* (OPC:1:Reset Slave) *)
	ResetSlave					AT%Q*	:	UINT;	(* (OPC:1:Reset Master) *)

	Kommando: 			INT;

	InputWord:			WORD;

(* Nach dem Einschalten, bzw. nach einem RESET *)
(*==========================================================================*)
IF (EStopReset=1) THEN			(* Wenn also Bit6 von <Input> gesetzt ist *)
	Error_Ack   := 1;
	Restart     := 1;
	ResetSSPSVars := TRUE;
ELSE
	Error_Ack := 0;
	Restart   := 0;
	ResetSSPSVars := FALSE;
END_IF;

(* Normalbetrieb *)
(*IF StatusBit9 AND StatusBit10 AND StatusBit11 THEN*)
(*==========================================================================*)
	EStopStatus:=CSETBIT32(EStopStatus,0,StatusBit0);
	EStopStatus:=CSETBIT32(EStopStatus,1,StatusBit1);
	EStopStatus:=CSETBIT32(EStopStatus,2,StatusBit2);
	EStopStatus:=CSETBIT32(EStopStatus,3,StatusBit3);
	EStopStatus:=CSETBIT32(EStopStatus,4,StatusBit4);
	EStopStatus:=CSETBIT32(EStopStatus,5,StatusBit5);
	EStopStatus:=CSETBIT32(EStopStatus,6,StatusBit6);
	EStopStatus:=CSETBIT32(EStopStatus,7,StatusBit7);
	EStopStatus:=CSETBIT32(EStopStatus,8,StatusBit8);
	EStopStatus:=CSETBIT32(EStopStatus,9,StatusBit9);
	EStopStatus:=CSETBIT32(EStopStatus,10,StatusBit10);
	EStopStatus:=CSETBIT32(EStopStatus,11,StatusBit11);

	EStopStatus:=CSETBIT32(EStopStatus,13,StatusBit13);
	EStopStatus:=CSETBIT32(EStopStatus,14,StatusBit14);
	EStopStatus:=CSETBIT32(EStopStatus,15,StatusBit15);
	EStopStatus:=CSETBIT32(EStopStatus,16,StatusBit16);
	EStopStatus:=CSETBIT32(EStopStatus,17,StatusBit17);
	EStopStatus:=CSETBIT32(EStopStatus,18,StatusBit18);
	EStopStatus:=CSETBIT32(EStopStatus,19,StatusBit19);
	EStopStatus:=CSETBIT32(EStopStatus,20,StatusBit20);
	EStopStatus:=CSETBIT32(EStopStatus,21,StatusBit21);
	EStopStatus:=CSETBIT32(EStopStatus,22,StatusBit22);
	EStopStatus:=CSETBIT32(EStopStatus,23,StatusBit23);
	EStopStatus:=CSETBIT32(EStopStatus,24,StatusBit24);
	EStopStatus:=CSETBIT32(EStopStatus,25,StatusBit25);
	EStopStatus:=CSETBIT32(EStopStatus,26,StatusBit26);

	EStopStatus:=CSETBIT32(EStopStatus,28,StatusBit28);
	EStopStatus:=CSETBIT32(EStopStatus,29,StatusBit29);
	EStopStatus:=CSETBIT32(EStopStatus,30,StatusBit30);
	EStopStatus:=CSETBIT32(EStopStatus,31,StatusBit31);
(*END_IF*)
	EStopStatus:=CSETBIT32(EStopStatus,12,StatusBit12);
	EStopStatus:=CSETBIT32(EStopStatus,27,StatusBit27);

(* Fehlerfall *)
(*==========================================================================*)


(* Fehlerbehandlung *)
(*==========================================================================*)
(* warten auf Godot *)
(* RESET *)
IF Kommando > 0 THEN
	CASE Kommando OF

		1: (* Reset *)
			ResetMaster := 2#00100000;		(* Das setzt das Bit6 am Steuerwort was einen RESET auslöst *)
			ResetSlave  := 2#00000010;		(* Das setzt das Bit2 am Steuerwort was einen RESET auslöst *)
	END_CASE;
    Kommando := 0;
J"TcSystem.lib 1.7.11 10:22:02@
N&TcUtilities.lib 31.8.11 18:09:14@\^N"STANDARD.LIB 5.6.98 16:03:02@w5)oscat_basic_332.lib 9.6.11 23:25:28@H:MKCONVERTDCTIMETOPOS@

DCTIMESTRUCTE_EcAdressingType
E_EcFoeModeE_EcMbxProtTypeE_EcScanSlavesCommandStatus
ProductCode
ST_DriveRef
ST_EcCrcErrorST_EcCrcErrorEx
ST_EcHeaderST_EcLastProtErrInfoST_EcMasterStatistic
ST_EcMaxCmdST_EcScannedSlaveStatusST_EcSlaveConfigDataST_EcSlaveIdentityST_EcSlaveScannedDataST_EcSlaveStateST_EcSlaveStateBitsST_PlcDriveRefST_SoE_DriveRefST_TPCTYPE_CODE_XXDDDST_TPCTYPE_CODE_XXDDXDST_TPCTYPE_CODE_XXDXDDST_TPCTYPE_CODE_XXDXDXDT_DCTIME
T_DCTIME32T_HFoeCONVERTPOSTODCTIME@
DCTIME_TO_DCTIMESTRUCT@DCTIME_TO_FILETIME@DCTIME_TO_STRING@DCTIME_TO_SYSTEMTIME@
DCTIMESTRUCT_TO_DCTIME@F_CheckVendorId@&F_ConvBK1120CouplerStateToString@F_ConvExtTimeToDcTime@"F_ConvMasterDevStateToString@F_ConvProductCodeToString@
F_ConvSlaveStateToBits@
F_ConvSlaveStateToString@F_ConvStateToString@F_ConvTcTimeToDcTime@F_ConvTcTimeToExtTime@F_GetActualDcTime@F_GetCurDcTaskTime@F_GetCurDcTickTime@F_GetCurExtTime@
F_GetVersionTcEtherCAT@FB_EcCoESdoRead@FB_EcCoESdoReadEx@FB_EcCoESdoWrite@FB_EcCoESdoWriteEx@
FB_EcDcTickTimeBaseCalc@FB_EcDcTimeCtrl@
FB_EcDcTimeCtrl.A_GetDay@$FB_EcDcTimeCtrl.A_GetDayOfWeek@FB_EcDcTimeCtrl.A_GetHour@ FB_EcDcTimeCtrl.A_GetMicro@ FB_EcDcTimeCtrl.A_GetMilli@!FB_EcDcTimeCtrl.A_GetMinute@ FB_EcDcTimeCtrl.A_GetMonth@FB_EcDcTimeCtrl.A_GetNano@!FB_EcDcTimeCtrl.A_GetSecond@FB_EcDcTimeCtrl.A_GetYear@
FB_EcExtSyncCalcTimeDiff@FB_EcExtSyncCheck@FB_EcFoeAccess@FB_EcFoeClose@FB_EcFoeLoad@FB_EcFoeOpen@FB_EcGetAllSlaveAddr@FB_EcGetAllSlaveCrcErrors@
FB_EcGetAllSlaveStates@FB_EcGetConfSlaves@
FB_EcGetLastProtErrInfo@FB_EcGetMasterState@FB_EcGetScannedSlaves@FB_EcGetSlaveCount@FB_EcGetSlaveCrcError@
FB_EcGetSlaveCrcErrorEx@FB_EcGetSlaveIdentity@FB_EcGetSlaveState@FB_EcLogicalReadCmd@FB_EcLogicalWriteCmd@FB_EcMasterFrameStatistic@'FB_EcMasterFrameStatisticClearCRC@*FB_EcMasterFrameStatisticClearFrames@+FB_EcMasterFrameStatisticClearTxRxErr@FB_EcPhysicalReadCmd@FB_EcPhysicalWriteCmd@FB_EcReqMasterState@FB_EcReqSlaveState@FB_EcSetMasterState@FB_EcSetSlaveState@FB_EcSoERead@FB_EcSoEWrite@FB_SoERead_ByDriveRef@
FB_SoEWrite_ByDriveRef@FILETIME_TO_DCTIME@STRING_TO_DCTIME@SYSTEMTIME_TO_DCTIME@Globale_Variablen@
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
SHR32@Global_Variables@(ßARG_TO_CSVFIELD@>
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
TC_Stop@TC_SysLatency@TIME_TO_OTSTRUCT@UInt32x32To64@UINT64_TO_LREAL@UINT64_TO_STRING@UInt64Add64@UInt64Add64Ex@UInt64And@UInt64Cmp64@UInt64Div16Ex@UInt64Div64@UInt64Div64Ex@UInt64isZero@UInt64Limit@UInt64Max@UInt64Min@UInt64Mod64@UInt64Mul64@UInt64Mul64Ex@UInt64Not@UInt64Or@UInt64Rol@UInt64Ror@UInt64Shl@UInt64Shr@UInt64Sub64@UInt64Xor@ULARGE_INTEGER@ULARGE_TO_LARGE@WORD_TO_FIX16@WritePersistentData@Global_Variables@CONCAT@	CTD@	CTU@
CTUD@
DELETE@
F_TRIG@
FIND@
INSERT@
LEFT@	LEN@	MID@
R_TRIG@
REPLACE@
RIGHT@RS@
SEMA@SR@	TOF@	TON@TP@Global Variables 0@"
_ARRAY_ABS@CALENDARCOMPLEXCONSTANTS_LANGUAGECONSTANTS_LOCATIONCONSTANTS_MATHCONSTANTS_PHYSCONSTANTS_SETUPESR_DATAFRACTION
HOLIDAY_DATAREAL2SDT
TIMER_EVENTVECTOR_3_ARRAY_ADD@_ARRAY_INIT@_ARRAY_MEDIAN@_ARRAY_MUL@_ARRAY_SHUFFLE@_ARRAY_SORT@_BUFFER_CLEAR@_BUFFER_INIT@_BUFFER_INSERT@_BUFFER_UPPERCASE@
_RMP_B@_RMP_NEXT@
_RMP_W@_STRING_TO_BUFFER@
A_TRIG@
ACOSH@
ACOTH@
ALARM_2@
ASINH@
ASTRO@
ATAN2@
ATANH@
B_TRIG@
BAND_B@BAR_GRAPH@BCDC_TO_INT@
BETA@BFT_TO_MS@BIN_TO_BYTE@BIN_TO_DWORD@
BINOM@BIT_COUNT@BIT_LOAD_B@BIT_LOAD_B2@BIT_LOAD_DW@BIT_LOAD_DW2@BIT_LOAD_W@BIT_LOAD_W2@BIT_OF_DWORD@BIT_TOGGLE_B@BIT_TOGGLE_DW@BIT_TOGGLE_W@BUFFER_COMP@BUFFER_SEARCH@BUFFER_TO_STRING@BYTE_OF_BIT@BYTE_OF_DWORD@BYTE_TO_BITS@BYTE_TO_GRAY@BYTE_TO_RANGE@BYTE_TO_STRB@BYTE_TO_STRH@
C_TO_F@
C_TO_K@
CACOS@
CACOSH@
CADD@CALENDAR_CALC@CALIBRATE@CAPITALIZE@
CASIN@
CASINH@
CATAN@
CATANH@
CCOSH@
CEIL2@
CLK_DIV@
CLK_N@
CLK_PRG@CLK_PULSE@
CONE_V@CONTROL_SET1@CONTROL_SET2@
CRC_GEN@
CSINH@
CSQRT@
CTANH@
CTRL_IN@CTRL_OUT@
CYCLE_4@CYCLE_TIME@
D_TRIG@
D_TRUNC@DATE_ADD@DAY_OF_DATE@DAY_OF_MONTH@DAY_OF_WEEK@DAY_OF_YEAR@DAY_TO_TIME@DAYS_DELTA@DAYS_IN_MONTH@DAYS_IN_YEAR@
DEC_2@
DEC_4@
DEC_8@DEC_TO_BYTE@DEC_TO_DWORD@DEC_TO_INT@	DEG@DEG_TO_DIR@DEL_CHARS@
DELAY@
DELAY_4@
DT_SIMU@DT_TO_SDT@DT_TO_STRF@DW_TO_REAL@DWORD_OF_BYTE@DWORD_OF_WORD@DWORD_TO_STRB@DWORD_TO_STRF@DWORD_TO_STRH@
ENERGY@	ERF@
EVENTS@
EXP10@
F_LIN@
F_LIN2@
F_POLY@
F_POWER@
F_QUAD@
F_TO_C@
F_TO_OM@
F_TO_PT@
FF_D2E@
FF_D4E@
FF_DRE@
FF_JKE@
FF_RSE@	FIB@
FIFO_16@
FIFO_32@
FINDP@	FIX@FLOAT_TO_REAL@
FLOOR@
FLOOR2@FLOW_CONTROL@FLOW_METER@
FRACT@
FRMP_B@FSTRING_TO_BYTE@FSTRING_TO_DT@FSTRING_TO_DWORD@FSTRING_TO_MONTH@FSTRING_TO_WEEK@FSTRING_TO_WEEKDAY@
FT_IMP@
FT_INT@
FT_INT2@FT_MIN_MAX@
FT_PD@
FT_PDT1@
FT_PI@
FT_PID@
FT_PIDW@FT_PIDWL@
FT_PIW@
FT_PIWL@FT_Profile@
FT_PT1@
FT_PT2@
FT_RMP@
FT_TN16@
FT_TN64@
FT_TN8@
GAMMA@
GAUSS@
GAUSSCD@	GCD@	GDF@
GEN_BIT@GEN_PULSE@
GEN_PW2@
GEN_RDM@
GEN_RDT@
GEN_RMP@
GEN_SIN@
GEN_SQ@
GEN_SQR@GEO_TO_DEG@
GOLD@GRAY_TO_BYTE@HEX_TO_BYTE@HEX_TO_DWORD@
HOLIDAY@
HOUR@HOUR_OF_DT@HOUR_TO_TIME@HOUR_TO_TOD@
HYPOT@
HYST_1@
HYST_2@
HYST_3@	INC@
IS_CC@
IS_CTRL@
IS_NCC@
ISC_HEX@ISC_LOWER@
ISC_NUM@ISC_UPPER@
JD2000@
LENGTH@LINEAR_INT@LIST_ADD@LIST_CLEAN@LIST_GET@LIST_INSERT@LIST_LEN@LIST_NEXT@LIST_RETRIEVE@LIST_RETRIEVE_LAST@LOWERCASE@
LTCH_4@LTIME_TO_UTC@	M_D@	M_T@
MATRIX@
METER@METER_STAT@
MINUTE@MINUTE_OF_DT@MINUTE_TO_TIME@
MIRROR@	MIX@
MODR@MONTH_BEGIN@MONTH_END@MONTH_OF_DATE@MONTH_TO_STRING@MS_TO_BFT@MS_TO_KMH@
MUL_ADD@MULTI_IN@
MULTIME@
MUX_2@
MUX_4@
MUX_R2@
MUX_R4@
NEGX@OCT_TO_BYTE@OCT_TO_DWORD@
OFFSET@
OFFSET2@
OM_TO_F@
ONTIME@OSCAT_VERSION@OVERRIDE@
PARITY@
PARSET@
PARSET2@
PERIOD@
PERIOD2@PIN_CODE@
PLC_PRG@POLYNOM_INT@PRESSURE@
PT_TO_F@
PWM_DC@
PWM_PW@
R2_ABS@
R2_ADD@
R2_ADD2@
R2_MUL@
R2_SET@	RAD@RANGE_TO_BYTE@RANGE_TO_WORD@	RDM@
RDMDW@REAL_TO_DW@REAL_TO_FRAC@REAL_TO_STRF@
REFLECT@REFRACTION@REPLACE_ALL@REPLACE_CHARS@REPLACE_UML@
RES_NI@
RES_NTC@
RES_PT@
RES_SI@
REVERSE@
ROUND@
RTC_2@
RTC_MS@
SCALE@
SCALE_D@
SECOND@SECOND_OF_DT@SECOND_TO_TIME@SEL2_OF_3@SEL2_OF_3B@SELECT_8@SENSOR_INT@SEQUENCE_4@SEQUENCE_64@SEQUENCE_8@SET_DATE@
SET_DT@
SIGMOID@
SIGN_I@
SIGN_R@
SQRTN@
STAIR@
STAIR2@STATUS_TO_ESR@
STORE_8@SUN_MIDDAY@
TC_MS@
TC_US@
TEMP_NI@TEMP_NTC@
TEMP_PT@
TEMP_SI@TEMPERATURE@
TICKER@TIMECHECK@
TOF_1@
TOGGLE@
TONOF@
TP_1D@
TRIM1@
TRIME@
TUNE2@UPPERCASE@UTC_TO_LTIME@
V3_ABS@
V3_ADD@
V3_ANG@
V3_DPRO@
V3_NORM@
V3_NUL@
V3_PAR@
V3_REV@
V3_SMUL@
V3_SUB@
V3_XANG@
V3_XPRO@
V3_YANG@
V3_ZANG@WEEKDAY_TO_STRING@
WINDOW@
MAIN.CabTemperatureUI
MAIN.SyncPosIstPosSoll
