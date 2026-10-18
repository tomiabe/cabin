export type Seat = {
  id: string;
  row: number;
  column: 'A' | 'B' | 'C' | 'D';
  x: number;
  y: number;
  z: number;
  type: 'window' | 'aisle';
  available: boolean;
  legroom: string;
  price: number;
};

export type SeatManifest = {
  seatCount: number;
  cabinLength: number;
  cabinWidth: number;
  seats: Seat[];
};

export type View = 'explore' | 'overview' | 'inspect' | 'sit' | 'walk';
