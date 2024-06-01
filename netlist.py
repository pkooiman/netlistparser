#! /usr/bin/env python3.9

from dataclasses import dataclass
from itertools   import chain
import argparse

@dataclass
class Pin:
    designator: str
    pin: int

@dataclass
class Net:
    name: str
    pins: list[Pin]


@dataclass
class Component:
    designator: str
    name: str
    package: str
    pin_nets: dict[int, Net]



class Design:
    Components: dict[str, Component]
    Nets: dict[str, Net]
    PARTNAMECOLWIDTH = 16
    PARTPACAKGECOLWIDTH = 17

    def __init__(self) -> None:
        self.Components = {}
        self.Nets = {}
        pass

    def ReadPartlist(self, lines: list[str]) -> int:
        if not lines[0].startswith('PARTS LIST'):
                print('Expected "PARTS LIST", wrong file?')
                return 0

        for index, l in enumerate(lines[1:]):
            l = l.lstrip('\x0c')
            if l.rstrip('\n') == 'EOS':
                #index 0 is line [1] here so add two to get line after EOS
                return index + 2
            name = l[:self.PARTNAMECOLWIDTH].rstrip()
            package = l[self.PARTNAMECOLWIDTH:self.PARTNAMECOLWIDTH+self.PARTPACAKGECOLWIDTH].rstrip()
            designators = l[self.PARTNAMECOLWIDTH+self.PARTPACAKGECOLWIDTH:].rstrip().split()

            if name and not name.startswith(' '):
                for d in designators:
                    if d in self.Components:
                        print(f"Error! Designator {d} already defined")
                        return 0
                    compo = Component(d, name, package, {})
                    self.Components[d] = compo



    def ReadNetlist(self, lines: list[str]) -> int:
        if not lines[0].startswith('NET LIST'):
                print('Expected "NET LIST", wrong file?')
                return 0

        curnet: Net
        curnet = None
        for index, l in enumerate(lines[1:]):
            l = l.lstrip('\x0c').rstrip(' $\n')
            if not l:
                continue
            if l.rstrip('\n') == 'EOS':
                #index 0 is line [1] here so add two to get line after EOS
                return index + 2


            if l.startswith('NODE'):
                netname = l.split()[1]
                if not netname in self.Nets:
                    curnet = Net(netname, [])
                    self.Nets[curnet.name] = curnet
                else:
                    curnet = self.Nets[netname]


            else:
                l = l[4:]
                for i, c in enumerate(l[::12]):
                    comp_pin = l[i*12:(i+1) * 12]
                    designator, pin = comp_pin.split()
                    if not curnet:
                        print(f"Error! Found component {designator} but no current net")
                        return 0
                    curnet.pins.append(Pin(designator, int(pin)))


    def BuildRef(self):
        for net in self.Nets.values():
            for pin in net.pins:
                comp = self.Components[pin.designator]
                if pin.pin in comp.pin_nets:
                    print(f"Error, duplicate pin {pin.pin} for component {comp.name}")
                comp.pin_nets[pin.pin] = net

    def ReadCadTemp(self, filename: str) -> bool:
        with open(filename, 'rt') as ct:
            lines = ct.readlines()
        nextindex = self.ReadPartlist(lines)

        self.ReadNetlist(lines[nextindex:])
        self.BuildRef()

    def GetComponent(self, designator: str) -> Component:
        if not designator in self.Components:
            return None
        return self.Components[designator]

#---------------------------------------------------------------------------
# planned_output = { pin_no -> { name: ..., destinations: [...] } }

NOT_CONNECTED = '(n/c)'

def print_pin_output(planned_output, min_pin = 1, max_pin = None):
    max_name_len       = max(map(lambda e: len(e['name']), chain(planned_output.values(), [{'name': NOT_CONNECTED}])))
    all_destinations   = list(chain.from_iterable((p.get('destinations', []) for p in planned_output.values())))
    max_designator_len = max(map(lambda e: len(e['designator']), chain(all_destinations, [{'designator': 'ABCD'}])))

    if not max_pin:
        max_pin = max(planned_output.keys())

    for pin_no in range(min_pin, (max_pin+1)):
        pin_data     = planned_output.get(pin_no, {'name': NOT_CONNECTED, 'connected': False})
        name         = pin_data['name']
        destinations = pin_data.get('destinations', None)

        print(f"{name:<{max_name_len}} {pin_no:>2d}", end=' ')
        if destinations:
            print("->", " / ".join((
                f"{p['designator']:<{max_designator_len}} {p['pin']:>2d}"
                for p in destinations
            )))
        else:
            if pin_data.get('connected', True):
                print(f"   (connections not listed for {name})")
            else:
                print()    # Omit noise for not connected pins


def print_pin_netlist(d: Design, c: Component, pin_no: int) -> None:
    if pin_no in c.pin_nets:
        net = c.pin_nets[pin_no]
        planned_output = { pin_no: { 'name': net.name } }

        if net.name not in ('GND', 'VCC'):
            planned_output[pin_no]['destinations'] = [
                { 'designator': connectedpin.designator,
                  'name':       d.GetComponent(connectedpin.designator).name,
                  'pin':        connectedpin.pin }
                for connectedpin in net.pins
                if not (connectedpin.designator == c.designator and connectedpin.pin == pin_no)
            ]
    else:
        planned_output = {}         # Place holder for "not present"

    print_pin_output(planned_output, pin_no, pin_no)


def print_component_netlist(d: Design, c: Component) -> None:
    planned_output = {}    # pin_no -> { name: ..., destinations: [...] }

    # Collect output destinations
    for pin_no, net in sorted(c.pin_nets.items()):
        planned_output[pin_no] = { 'name': net.name }

        if net.name not in ('GND', 'VCC'):
            planned_output[pin_no]['destinations'] = [
                { 'designator': connectedpin.designator,
                  'name':       d.GetComponent(connectedpin.designator).name,
                  'pin':        connectedpin.pin }
                for connectedpin in net.pins
                if not (connectedpin.designator == c.designator and connectedpin.pin == pin_no)
            ]

    print_pin_output(planned_output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('designator')
    parser.add_argument('pin', nargs="?", type=int)
    args = parser.parse_args()

    d = Design()
    d.ReadCadTemp('cad.temp')

    c = d.GetComponent(args.designator)
    if not c:
        print(f"Designator {args.designator} not found")
        exit()

    if args.pin:
        pin_msg = f" -- pin {args.pin} only"
    else:
        pin_msg =  ""

    print(f"{c.designator}: {c.name} ({c.package}){pin_msg}")
    print()

    if args.pin:
        print_pin_netlist(d, c, args.pin)
    else:
        print_component_netlist(d, c)

if __name__ == '__main__':
    main()
