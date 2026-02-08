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

  describe('Grid Dimension Validation', () => {
    it('should warn on small grid dimensions', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="75"/><Cell value="80"/></Row>
              <Row label="2"><Cell value="78"/><Cell value="82"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.grid?.some(w => w.includes('too small'))).toBe(true);
    });

    it('should warn on uncommon grid patterns', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              ${Array.from({length: 15}, (_, i) => `<Col label="${(i+1)*10}"/>`).join('')}
            </Columns>
            <Rows units="RPMx1000">
              ${Array.from({length: 20}, (_, i) => `<Row label="${i+1}">${Array.from({length: 15}, () => '<Cell value="80"/>').join('')}</Row>`).join('')}
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.grid?.some(w => w.includes('Uncommon grid size'))).toBe(true);
    });
  });

  describe('Value Range Validation', () => {
    it('should warn on unusually low VE values', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="40"/><Cell value="42"/><Cell value="45"/><Cell value="48"/><Cell value="50"/></Row>
              <Row label="2"><Cell value="42"/><Cell value="44"/><Cell value="46"/><Cell value="48"/><Cell value="50"/></Row>
              <Row label="3"><Cell value="43"/><Cell value="45"/><Cell value="47"/><Cell value="49"/><Cell value="51"/></Row>
              <Row label="4"><Cell value="44"/><Cell value="46"/><Cell value="48"/><Cell value="50"/><Cell value="52"/></Row>
              <Row label="5"><Cell value="45"/><Cell value="47"/><Cell value="49"/><Cell value="51"/><Cell value="53"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.values?.some(w => w.includes('low VE values'))).toBe(true);
    });

    it('should warn on unusually high VE values', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="125"/><Cell value="128"/><Cell value="130"/><Cell value="132"/><Cell value="135"/></Row>
              <Row label="2"><Cell value="125"/><Cell value="128"/><Cell value="130"/><Cell value="132"/><Cell value="135"/></Row>
              <Row label="3"><Cell value="125"/><Cell value="128"/><Cell value="130"/><Cell value="132"/><Cell value="135"/></Row>
              <Row label="4"><Cell value="125"/><Cell value="128"/><Cell value="130"/><Cell value="132"/><Cell value="135"/></Row>
              <Row label="5"><Cell value="125"/><Cell value="128"/><Cell value="130"/><Cell value="132"/><Cell value="135"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.values?.some(w => w.includes('high VE values'))).toBe(true);
    });

    it('should warn on extreme AFR values', () => {
      const xml = `
        <PVV>
          <Item name="Air-Fuel Ratio" units="AFR">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="10.5"/><Cell value="10.8"/><Cell value="11.0"/><Cell value="11.2"/><Cell value="11.5"/></Row>
              <Row label="2"><Cell value="10.5"/><Cell value="10.8"/><Cell value="11.0"/><Cell value="11.2"/><Cell value="11.5"/></Row>
              <Row label="3"><Cell value="10.5"/><Cell value="10.8"/><Cell value="11.0"/><Cell value="11.2"/><Cell value="11.5"/></Row>
              <Row label="4"><Cell value="10.5"/><Cell value="10.8"/><Cell value="11.0"/><Cell value="11.2"/><Cell value="11.5"/></Row>
              <Row label="5"><Cell value="10.5"/><Cell value="10.8"/><Cell value="11.0"/><Cell value="11.2"/><Cell value="11.5"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.values?.some(w => w.includes('rich AFR'))).toBe(true);
    });
  });

  describe('Bin Monotonicity Validation', () => {
    it('should warn on non-ascending RPM bins', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="75"/><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="85"/></Row>
              <Row label="3"><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/></Row>
              <Row label="2"><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/></Row>
              <Row label="4"><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/><Cell value="90"/></Row>
              <Row label="5"><Cell value="85"/><Cell value="87"/><Cell value="89"/><Cell value="91"/><Cell value="93"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.bins?.some(w => w.includes('not in ascending order'))).toBe(true);
    });

    it('should warn on duplicate MAP bins', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="50"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="75"/><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="85"/></Row>
              <Row label="2"><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/></Row>
              <Row label="3"><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/></Row>
              <Row label="4"><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/><Cell value="90"/></Row>
              <Row label="5"><Cell value="85"/><Cell value="87"/><Cell value="89"/><Cell value="91"/><Cell value="93"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.bins?.some(w => w.includes('duplicate'))).toBe(true);
    });
  });

  describe('Data Quality Validation', () => {
    it('should warn on tables with many zeros', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/></Row>
              <Row label="2"><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="85"/></Row>
              <Row label="3"><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/></Row>
              <Row label="4"><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/></Row>
              <Row label="5"><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/><Cell value="0"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.quality?.some(w => w.includes('zero'))).toBe(true);
    });
  });

  describe('Front/Rear Comparison', () => {
    it('should warn if front and rear tables differ significantly', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="75"/><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="85"/></Row>
              <Row label="2"><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/></Row>
              <Row label="3"><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/></Row>
              <Row label="4"><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/><Cell value="90"/></Row>
              <Row label="5"><Cell value="85"/><Cell value="87"/><Cell value="89"/><Cell value="91"/><Cell value="93"/></Row>
            </Rows>
          </Item>
          <Item name="VE (MAP based/Rear Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="95"/><Cell value="98"/><Cell value="100"/><Cell value="102"/><Cell value="105"/></Row>
              <Row label="2"><Cell value="98"/><Cell value="100"/><Cell value="102"/><Cell value="104"/><Cell value="106"/></Row>
              <Row label="3"><Cell value="100"/><Cell value="102"/><Cell value="104"/><Cell value="106"/><Cell value="108"/></Row>
              <Row label="4"><Cell value="102"/><Cell value="104"/><Cell value="106"/><Cell value="108"/><Cell value="110"/></Row>
              <Row label="5"><Cell value="105"/><Cell value="107"/><Cell value="109"/><Cell value="111"/><Cell value="113"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.comparison?.some(w => w.includes('differ significantly'))).toBe(true);
    });

    it('should warn if front and rear tables are nearly identical', () => {
      const xml = `
        <PVV>
          <Item name="VE (MAP based/Front Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="75"/><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="85"/></Row>
              <Row label="2"><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/></Row>
              <Row label="3"><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/></Row>
              <Row label="4"><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/><Cell value="90"/></Row>
              <Row label="5"><Cell value="85"/><Cell value="87"/><Cell value="89"/><Cell value="91"/><Cell value="93"/></Row>
            </Rows>
          </Item>
          <Item name="VE (MAP based/Rear Cyl)" units="%">
            <Columns units="Kilopascals">
              <Col label="30"/><Col label="50"/><Col label="70"/><Col label="90"/><Col label="100"/>
            </Columns>
            <Rows units="RPMx1000">
              <Row label="1"><Cell value="75"/><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="85"/></Row>
              <Row label="2"><Cell value="78"/><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/></Row>
              <Row label="3"><Cell value="80"/><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/></Row>
              <Row label="4"><Cell value="82"/><Cell value="84"/><Cell value="86"/><Cell value="88"/><Cell value="90"/></Row>
              <Row label="5"><Cell value="85"/><Cell value="87"/><Cell value="89"/><Cell value="91"/><Cell value="93"/></Row>
            </Rows>
          </Item>
        </PVV>
      `;
      
      const result = parsePVV(xml);
      
      expect(result.validationWarnings?.comparison?.some(w => w.includes('nearly identical'))).toBe(true);
    });
  });
});
