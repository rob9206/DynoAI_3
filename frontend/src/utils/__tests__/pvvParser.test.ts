import { parsePVV } from '../pvvParser';

describe('pvvParser', () => {
  it('should prefer MAP-based VE tables over TPS-based', () => {
    const xml = `
      <PVV>
        <Item name="VE (TPS based/Front Cyl)" units="%">
          <Columns units="%">
            <Col label="0"/><Col label="100"/>
          </Columns>
          <Rows units="RPMx1000">
            <Row label="1"><Cell value="80"/><Cell value="90"/></Row>
          </Rows>
        </Item>
        <Item name="VE (MAP based/Front Cyl)" units="%">
          <Columns units="Kilopascals">
            <Col label="30"/><Col label="100"/>
          </Columns>
          <Rows units="RPMx1000">
            <Row label="1"><Cell value="75"/><Cell value="95"/></Row>
          </Rows>
        </Item>
      </PVV>
    `;
    
    const result = parsePVV(xml);
    
    expect(result.veFront?.name).toBe('VE (MAP based/Front Cyl)');
    expect(result.veFront?.columns).toEqual([30, 100]);
  });

  it('should detect MAP-based table by column units when name is generic', () => {
    const xml = `
      <PVV>
        <Item name="VE (TPS based/Front Cyl)" units="%">
          <Columns units="%">
            <Col label="0"/><Col label="100"/>
          </Columns>
          <Rows units="RPMx1000">
            <Row label="1"><Cell value="80"/><Cell value="90"/></Row>
          </Rows>
        </Item>
        <Item name="VE Front" units="%">
          <Columns units="Kilopascals">
            <Col label="30"/><Col label="100"/>
          </Columns>
          <Rows units="RPMx1000">
            <Row label="1"><Cell value="75"/><Cell value="95"/></Row>
          </Rows>
        </Item>
      </PVV>
    `;
    
    const result = parsePVV(xml);
    
    expect(result.veFront?.name).toBe('VE Front');
    expect(result.veFront?.columnUnits).toBe('Kilopascals');
  });

  it('should warn if only TPS-based tables are available', () => {
    const xml = `
      <PVV>
        <Item name="VE (TPS based/Front Cyl)" units="%">
          <Columns units="%">
            <Col label="0"/><Col label="100"/>
          </Columns>
          <Rows units="RPMx1000">
            <Row label="1"><Cell value="80"/><Cell value="90"/></Row>
          </Rows>
        </Item>
      </PVV>
    `;
    
    const result = parsePVV(xml);
    
    expect(result.veFront?.name).toBe('VE (TPS based/Front Cyl)');
    expect(result.parseErrors.some(e => e.includes('TPS-based'))).toBe(true);
  });

  it('should handle rear cylinder tables with same logic', () => {
    const xml = `
      <PVV>
        <Item name="VE (TPS based/Rear Cyl)" units="%">
          <Columns units="%">
            <Col label="0"/><Col label="100"/>
          </Columns>
          <Rows units="RPMx1000">
            <Row label="1"><Cell value="80"/><Cell value="90"/></Row>
          </Rows>
        </Item>
        <Item name="VE (MAP based/Rear Cyl)" units="%">
          <Columns units="Kilopascals">
            <Col label="30"/><Col label="100"/>
          </Columns>
          <Rows units="RPMx1000">
            <Row label="1"><Cell value="75"/><Cell value="95"/></Row>
          </Rows>
        </Item>
      </PVV>
    `;
    
    const result = parsePVV(xml);
    
    expect(result.veRear?.name).toBe('VE (MAP based/Rear Cyl)');
    expect(result.veRear?.columns).toEqual([30, 100]);
  });
});
