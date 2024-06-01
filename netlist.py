from dataclasses import dataclass
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
        
    

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('designator')
    parser.add_argument('pin', nargs="?", type=int)
    args = parser.parse_args()

    if args.designator:
        d = Design()
        d.ReadCadTemp('cad.temp')
        c = d.GetComponent(args.designator)
        if not c:
            print(f"Designator {args.designator} not found")
            exit()
        print(f"{c.designator}: {c.name} ({c.package})")
        if args.pin:
            if not args.pin in c.pin_nets:
                print(f"Pin {args.pin} not found for designator {args.designator}")
                exit()
            net = c.pin_nets[args.pin]
            print(f"Pin {args.pin}: Net {net.name} connects to:")
            for pin in net.pins:
                if not (pin.designator == c.designator and pin.pin == args.pin):
                    print(f"\t{pin.designator} ({d.GetComponent(pin.designator).name}): pin {pin.pin}")
        else:
            for pin_no, net in sorted(c.pin_nets.items()):

                print(f"{net.name:20}{pin_no:2} -> ", end = '')
                #print(f"Pin {pin_no}: Net {net.name} connects to:")
                if net.name != 'GND' and net.name != 'VCC':
                    for connectedpin in net.pins:
                        if not (connectedpin.designator == c.designator and connectedpin.pin == pin_no):
                            print(f"{connectedpin.designator:5} {connectedpin.pin:2}   ", end ='')
                    
                else:
                    print(f"Connections not listed for net {net.name}..", end = '')
                print('')
            