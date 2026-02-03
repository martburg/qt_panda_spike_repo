class Decode():
    def Decode(self,value): 
        if value=="SIMUL":
            message=(0,"SIMUL","SIMUL",(0,200,0))
            
            state1="Output powered: SIMUL"
            state2="AMP ready: SIMUL"
            state3="Referenced: SIMUL"
            state4="In Position: SIMUL"
            state5="Break lifted: SIMUL"
            state6="Right End Switch contacted: SIMUL"
            state7="Left End Switch contacted: SIMUL"
            
            bit0=1
            bit1=1
            bit2=1
            bit3=1
            bit4=1
            bit6=1
            bit7=1
        elif value=="0":
            message=(0,"NA","NA",(255,255,255))
            
            state1="Output powered: NoConn"
            state2="AMP ready: NoConn"
            state3="Referenced: NoConn"
            state4="In Position: NoConn"
            state5="Break lifted: NoConn"
            state6="Right End Switch contacted: NoConn"
            state7="Left End Switch contacted: NoConn"
            
            bit0=0
            bit1=0
            bit2=0
            bit3=0
            bit4=0
            bit6=0
            bit7=0            

        else:
            value = int(value) 
            if value%2==0:
                state1 = "Output powered: 0"
                bit0=0
            else:
                state1 = "Output powered: 1"
                bit0=1
            if (value>>1)%2==0:
                state2 = "AMP ready: 0"
                bit1=0
            else:
                state2 = "AMP ready: 1"
                bit1=1
            if (value>>2)%2 ==0:
                state3 = "Referenced: 0"
                bit2=0
            else:
                state3 = "Referenced: 1"
                bit2=1
            if (value>>3)%2==0:
                state4 = "In Position: 0"
                bit3=0
            else:
                state4 = "In Position: 1"
                bit3=1
            if (value>>4)%2==0:
                state5="Brake lifted: 0"
                bit4=0
            else:
                state5="Brake lifted: 1"
                bit4=1
            if (value>>6)%2==0:
                state6="Right e-switch contacted: 0"
                bit6=0
            else:
                state6="Right e-switch contacted: 1"
                bit6=1
            if (value>>7)%2==0:
                state7="Left e-switch contacted: 0"
                bit7=0
            else:
                state7="Left e-switch contacted: 1"
                bit7=1
            if (value>>5)%2==0:
             #   Fehler Bit nicht gesetzt
                Zustand = value>>8
                if Zustand==0:
                    message =  (0,str(Zustand),"Not Ready",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif Zustand==1:
                    message =  (0,str(Zustand),"Locked",(0,150,0))#txtCtrl gehoert Rot eingefaerbt
                elif Zustand==2:
                    message =  (0,str(Zustand),"Not Enabled",(255,240,0))#txtCtrl gehoert Rot eingefaerbt
                elif Zustand==3:
                    message =  (0,str(Zustand),"Heating",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==4:
                    message =  (0,str(Zustand),"VCC-Mode",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==5:
                    message =  (0,str(Zustand),"Guider",(0,150,0))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==6:
                    message =  (0,str(Zustand),"M-Regelung",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==7:
                    message =  (0,str(Zustand),"Holding",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==8:
                    message =  (0,str(Zustand),"Factory Reset",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==9:
                    message =  (0,str(Zustand),"Stops contacted",(255,255,255)) #txtCtrl gehoert Neutral eingefaerbt 
                elif Zustand==10:
                    message =  (0,str(Zustand),"Ready",(0,150,0))#SEW-Tech Option  gehoert Gruen eingefaerbt
                elif Zustand==11:
                    message =  (0,str(Zustand),"Referenzfahrt",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==12:
                    message =  (0,str(Zustand),"Fangen",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==13:
                    message =  (0,str(Zustand),"Geber einmessen",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==14:
                    message =  (0,str(Zustand),"Fehler",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==15:
                    message =  (0,str(Zustand),"Handbetrieb",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==16:
                    message =  (0,str(Zustand),"TimeOut",(255,255,255))#txtCtrl gehoert Neutral eingefaerbt
                elif Zustand==17:
                    message =  (0,str(Zustand),"Save Stop",(250,198,12))#txtCtrl gehoert Gelb eingefaerbt
                else:
                    message =  ("0",str(Zustand),"Unknown",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
            else:
                Zustand = value >> 8
                if Zustand==1:
                    message=("1",str(Zustand),"-Ueberstrom",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="3":
                    message=("1",str(Zustand),"-Erdschluss",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="4":
                    message=("1",str(Zustand),"-Bremschopper",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="6":
                    message=("1",str(Zustand),"-Netzphasenausfall",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                       
                elif str(Zustand)=="7":
                    message=("1",str(Zustand),"-Zwischenkreis Ueberspannung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="8":
                    message=("1",str(Zustand),"-Drehzahlueberwachung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="9":
                    message=("1",str(Zustand),"-Inbetriebnahme",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="10":
                    message=("1",str(Zustand),"-IPOS-ILLOP",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="11":
                    message=("1",str(Zustand),"-Uebertemperatur",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="13":
                    message=("1",str(Zustand),"-Steuerquelle",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="14":
                    message=("1",str(Zustand),"-Geber",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                        
                elif str(Zustand)=="17":
                    message=("1",str(Zustand),"-Stack Overflow",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="18":
                    message=("1",str(Zustand),"-Stack Underflow",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="19":
                    message=("1",str(Zustand),"-External NMI",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="20":
                    message=("1",str(Zustand),"-Undefined OP-Code",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="21":
                    message=("1",str(Zustand),"-Protection Fault",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="22":
                    message=("1",str(Zustand),"-Illegal Word Operand",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="23":
                    message=("1",str(Zustand),"-Illegal Instruction Access",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                        
                elif str(Zustand)=="24":
                    message=("1",str(Zustand),"-Illegal External Bus Access",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="25":
                    message=("1",str(Zustand),"-EEPROM",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="26":
                    message=("1",str(Zustand),"-Externe Klemme",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="27":
                    message=("1",str(Zustand),"-Endschalter fehlen",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="28":
                    message=("1",str(Zustand),"-Feldbus Timeout",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="29":
                    message=("1",str(Zustand),"-Endschalter angefahren",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="30":
                    message=("1",str(Zustand),"-Notstop Timout",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                        
                elif str(Zustand)=="31":
                    message=("1",str(Zustand),"-TF/TH Ausloeser",(255,0,0))#txtCtrl gehoert Rot eingefaerbt               
                elif str(Zustand)=="32":
                    message=("1",str(Zustand),"-IPOS-Index Overflow",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="33":
                    message=("1",str(Zustand),"-Sollwert Quelle",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="34":
                    message=("1",str(Zustand),"-Rampen Timeout",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="35":
                    message=("1",str(Zustand),"-Betriebsart",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="36":
                    message=("1",str(Zustand),"-Option Missing",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="37":
                    message=("1",str(Zustand),"-System Watchdog",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="38":
                    message=("1",str(Zustand),"-System Software",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                        
                elif str(Zustand)=="39":
                    message=("1",str(Zustand),"-Referenzfahrt",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="40":
                    message=("1",str(Zustand),"-Boot Synchronisation",(255,0,0))#txtCtrl gehoert Rot eingefaerbt               
                elif str(Zustand)=="41":
                    message=("1",str(Zustand),"-Watchdog Option",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="42":
                    message=("1",str(Zustand),"-Schleppfehler",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="43":
                    message=("1",str(Zustand),"-RS485 Timeout",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="44":
                    message=("1",str(Zustand),"-Geraeteauslastung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="45":
                    message=("1",str(Zustand),"-Initialisierung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                       
                elif str(Zustand)=="46":
                    message=("1",str(Zustand),"-Systembus 2 Timeout",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="47":
                    message=("1",str(Zustand),"-Systembus 1 Timeout",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="48":
                    message=("1",str(Zustand),"-Hardware DRS",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="77":
                    message=("1",str(Zustand),"-IPOS.Steuerwort",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="78":
                    message=("1",str(Zustand),"-IPOS.SW Endschalter",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="79":
                    message=("1",str(Zustand),"-Hardware Konfiguration",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="80":
                    message=("1",str(Zustand),"-RAM-Test",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="81":
                    message=("1",str(Zustand),"-Starting Kondition",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="82":
                    message=("1",str(Zustand),"-Ausgang offen",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                       
                elif str(Zustand)=="84":
                    message=("1",str(Zustand),"-Motorschutz",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="86":
                    message=("1",str(Zustand),"-Speichermodul",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="87":
                    message=("1",str(Zustand),"-Technologie Option",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="88":
                    message=("1",str(Zustand),"-Fangen",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="92":
                    message=("1",str(Zustand),"-DIP Geber Problem",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="93":
                    message=("1",str(Zustand),"-DIP Geber Fehler",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="94":
                    message=("1",str(Zustand),"-Checksum EEPROM",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                        
                elif str(Zustand)=="95":
                    message=("1",str(Zustand),"-DIP-Plausibilitaetsfehler",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="97":
                    message=("1",str(Zustand),"-Kopierfehler",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="98":
                    message=("1",str(Zustand),"-CRC Error",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="99":
                    message=("1",str(Zustand),"-IPOS.Rampenberechnung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="100":
                    message=("1",str(Zustand),"-Schwingungs Warnung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="101":
                    message=("1",str(Zustand),"-Schwingungs Fehler",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                elif str(Zustand)=="102":
                    message=("1",str(Zustand),"-Oelalterung Warnung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="103":
                    message=("1",str(Zustand),"-Oelalterung Fehler",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="104":
                    message=("1",str(Zustand),"-Oelalterung Ueberthemperatur",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="105":
                    message=("1",str(Zustand),"-Oelalterung Sensor",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="106":
                    message=("1",str(Zustand),"-Bremsen Verschleiss",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="107":
                    message=("1",str(Zustand),"-Netzkomponenten",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                        
                elif str(Zustand)=="108":
                    message=("1",str(Zustand),"-Fehler DCS",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="109":
                    message=("1",str(Zustand),"-Alarm DCS",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="110":
                    message=("1",str(Zustand),"-Error EX.Schutz",(255,0,0))#txtCtrl gehoert Rot eingefaerbt       
                elif str(Zustand)=="113":
                    message=("1",str(Zustand),"-Drahtbruch Analogeingang",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="116":
                    message=("1",str(Zustand),"-Timout MoviPLC",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="123":
                    message=("1",str(Zustand),"-Positionierunterbrechung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
                elif str(Zustand)=="124":
                    message=("1",str(Zustand),"-Umgebungsbedingungen",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                                        
                elif str(Zustand)=="196":
                    message=("1",str(Zustand),"-Leistungsteil",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="197":
                    message=("1",str(Zustand),"-Netz",(255,0,0))#txtCtrl gehoert Rot eingefaerbt                
                elif str(Zustand)=="199":
                    message=("1",str(Zustand),"-Zwischenkreisaufladung",(255,0,0))#txtCtrl gehoert Rot eingefaerbt        
                else:
                    message=("1",str(Zustand),"-Unknown Error",(255,0,0))#txtCtrl gehoert Rot eingefaerbt
        return ((message ,state1,state2,state3,state4,state5,state6,state7),(message,bit0,bit1,bit2,bit3,bit4,bit6,bit7))    
    