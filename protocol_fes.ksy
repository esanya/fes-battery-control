meta:
  id: fes
  file-extension: fes
  endian: le
seq:
  - id: beginchar
    contents: [0x55]
  - id: source
    type: u1
  - id: dest
    type: u1
  - id: msglen
    type: u1
  - id: payload
    size: msglen
  - id: checksum
    type: u2
    doc: CRC calculated by the Crc16Arc algorithm
  - id: endchar
    contents: [0xaa]
