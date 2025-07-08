# PrOPPlan #

## Operative Produktionsprogrammplanung durch selbstoptimierende Materialflusssimulation mittels Reinforcement Learning ##

Die zentrale Aufgabe der operativen Produktionsprogrammplanung (PPP) ist die Erstellung des Produktionsprogramms,
das festlegt, welche Produkte in welchen Mengen und in welchen Zeiträumen hergestellt werden.
Dabei auftretende, produktionstechnischen Fragestellungen werden typischerweise in aufeinander aufbauender Reihenfolge und unter Nutzung vom Fachwissen
menschlicher Planer*innen beantwortet. Die Folge sind nicht-optimale Lösungen aufgrund von konsekutiven Planungsannahmen sowie wiederkehrende Aufwände für Neu- und Anpassungsplanungen aufgrund von variabilitätsbedingten Änderungseinflüssen oder neu eingetroffenen Aufträgen.

Für ursprünglich human-zentrierte Aufgaben der operativen
PPP wird, mithilfe von ereignisdiskreten Materialflusssimulationen (MFS) und durch die im vergangenen
Jahrzehnt aufgekommenen Möglichkeiten künstlicher Intelligenz und maschinellen Lernens, eine Methodik zur Erzeugung von Empfehlungen für eine optimale
Lösung kohärenter Planungsaufgaben entwickelt. Konkret wird die Erstellung idealer Produktionsprogrammpläne untersucht,
wofür die integrierte Lösung von Reihenfolgenplanung, Losgrößenrechnung, Feinterminierung sowie Auftragsfreigabe
mithilfe intelligenter Verfahren betrachtet wird. Die Methodik wird für Szenarien des Projektbegleitenden Ausschuss
(PA) entwickelt, zur weiterführenden Verwendung generalisiert und vorhabenbegleitend in ein IT-Werkzeug überführt.

## Installationsanleitung / Installation ##

The program is developed using __Python 3.12.7__. Please create a virtual environment for using Propplan.

Requirements:

```
json
numpy
matplotlib
PyQt5
gymnasium
torch
nevergrad
ray
seaborn
tensorboard

```

Once the requirements are installed, you should be able to run the main user interface from your IDE:

```
user_interface.py
```

## Main idea ##

Propplan consists of 5 tabs:

1) Production resources
2) Product instructions
3) Order data
4) System simulation
5) AI optimization

To use reinforcement learning (RL), a simulation of the analyzed system is necessary. The required data are input in the tabs 1-4. Tabs 4 and 5 is where simulations can be run and performance of different control approaches examined.

### Production resources ###

*TODO: UML class diagrams of the data structure*

To simulate a production system, at minimum, the information about workstations is necessary. The more detailed the provided data, the more added value from RL (theoretically!). We need to answer the question: _what_ do we use to fulfill customer orders?

Propplan accepts very detailed information about objects involved in the dynamic behaviour of a production system, however most of the fields in the Production Resources tab are optional and have default values for the assumption that these fields are neglected in modeling. The depth of detail that users choose is dependent on the necessary effort to collect information about the production system.

### Product instructions ###

We can plan or schedule operations if we know _what_ needs to be produced, _how_ it is to be produced, _what_ components or raw materials are used and _how long_ the operations take. Propplan uses precedence graphs to represent both work plans and BOMs in a convenient way.

### Order data ###

Production schedules will vary significantly depending on the "pressure" from the consumers, which manifests itself in the order data (_what_ needs to be produced and _till when_).

### System simulation ###

*TODO: this is not finished yet*

Once we've specified everything in the 3 previous tabs and a couple other system-wide properties in tab 4, we can see how the system will behave using various control strategies, ranging from simple heuristics to advanced RL models (once they are trained). Propplan doesn't visualize a physical layout of production systems but focuses on the schedules (dynamic Gantt charts) instead.

### AI optimization ###

The idea is that separate simulation runs with specified control algorithms or models can be played in the tab 4 (System simulation), whereas tab 5 (AI optimization) will use said simulation environment hundreds of thousands if not millions of times to train RL models. AI optimization tab will also keep track of training runs.