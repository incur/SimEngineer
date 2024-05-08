# CIP Behälter

## CIP LB

### Zyklus 1
<!-- no toc -->
- [Init](#init)
- [Druckprüfung](#druckprüfung)
- [Container Zugabe](#container-zugabe)
- [Handzugabe](#handzugabe)
- [Rohstoffzugabe](#rohstoffzugabe)
- [Einlauf](#einlauf)
- [Sprühkugeln](#sprühkugeln)
- [Entleeren](#entleeren)

### Zyklus 2
<!-- no toc -->
- [Druckprüfung](#druckprüfung)
- [Container Zugabe](#container-zugabe)
- [Handzugabe](#handzugabe)
- [Rohstoffzugabe](#rohstoffzugabe)
- [Einlauf](#einlauf)
- [Sprühkugeln](#sprühkugeln)
- [Füllen](#füllen)
- [CIP Rührer](#cip-rührer)
- [Entleeren](#entleeren)
- [Abschluss](#abschluss)

## CIP AB

### Zyklus 1
<!-- no toc -->
- [Init](#init)
- [Druckprüfung](#druckprüfung)
- [Trans In](#trans-in)
- [Einlauf](#einlauf)
- [Fallrohr / Glas](#fallrohr--glas)
- [Sprühkugeln](#sprühkugeln)
- [Entleeren](#entleeren)

### Zyklus 2
<!-- no toc -->
- [Druckprüfung](#druckprüfung)
- [Trans In](#trans-in)
- [Einlauf](#einlauf)
- [Fallrohr / Glas](#fallrohr--glas)
- [Sprühkugeln](#sprühkugeln)
- [Füllen](#füllen)
- [CIP Rührer](#cip-rührer)
- [Entleeren](#entleeren)
- [Abschluss](#abschluss)

## Funktionen

### Init
- Entleeren -> Füllstand
- Nachlauf -> 190 sek.

### Druckprüfung
- Druck -> >= -0,2bar & <= 0,2bar

### Container Zugabe
- WFI UV043 -> 30m³/h & 60kg
- DRL -> 33 sek.

### Handzugabe
- WFI UV043 -> 30m³/h & 40kg
- DRL -> 33 sek.

### Rohstoffzugabe
- WFI UV043 -> 30m³/h & 60kg
- DRL -> 33 sek.

### Trans In
- WFI UV363 -> 10m³/h & 300 sek.
- DRL -> 33 sek.

### Fallrohr / Glas
- WFI UV043 -> 30m³/h & 300kg
- DRL -> 33 sek.

### Einlauf
- WFI UV043 -> 30m³/h & 80kg
- DRL -> 33 sek.

### Entleeren
- Leer -> füllstand + 60sec
- Nachlauf -> 180 sek.

### Sprühkugeln
- WFI UV043 -> 30m³/h & 300kg
- DRL -> 33 sek.

### Füllen
- WFI UV043 -> 30m³/h & Füllstand >= 0,5 m³
- DRL -> 35 sek.

### CIP Rührer
- Delay -> 300 sek.

### Abschluss
- Druckaufbau -> >= 1 bar
- Leer Drücken -> <= 0,5 bar