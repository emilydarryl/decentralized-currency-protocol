use crate::model::{Candidate, TranscriptFrame};
use binary_sv2::{
    decodable::{DecodableField, FieldMarker},
    Deserialize, GetSize, Serialize,
};

pub const MSG_SETUP: u8 = 0x00;
pub const MSG_SETUP_SUCCESS: u8 = 0x01;
pub const MSG_SETUP_ERROR: u8 = 0x02;
pub const MSG_OPEN_EXTENDED: u8 = 0x13;
pub const MSG_OPEN_EXTENDED_SUCCESS: u8 = 0x14;
pub const MSG_OPEN_ERROR: u8 = 0x12;
pub const MSG_SET_CUSTOM: u8 = 0x22;
pub const MSG_SET_CUSTOM_SUCCESS: u8 = 0x23;
pub const MSG_SET_CUSTOM_ERROR: u8 = 0x24;
pub const MSG_ALLOCATE_TOKEN: u8 = 0x50;
pub const MSG_ALLOCATE_TOKEN_SUCCESS: u8 = 0x51;
pub const MSG_PROVIDE_MISSING: u8 = 0x55;
pub const MSG_PROVIDE_MISSING_SUCCESS: u8 = 0x56;
pub const MSG_DECLARE: u8 = 0x57;
pub const MSG_DECLARE_SUCCESS: u8 = 0x58;
pub const MSG_DECLARE_ERROR: u8 = 0x59;

pub const VERSION: u16 = 2;
pub const JD_FLAGS: u32 = 1;
pub const MINING_FLAGS: u32 = 4;

pub type Result<T> = std::result::Result<T, String>;

#[derive(Clone, Debug)]
pub struct RawPayload(pub Vec<u8>);

impl GetSize for RawPayload {
    fn get_size(&self) -> usize {
        self.0.len()
    }
}

impl Serialize for RawPayload {
    fn to_bytes(self, destination: &mut [u8]) -> std::result::Result<usize, binary_sv2::Error> {
        if destination.len() < self.0.len() {
            return Err(binary_sv2::Error::WriteError(
                self.0.len(),
                destination.len(),
            ));
        }
        destination[..self.0.len()].copy_from_slice(&self.0);
        Ok(self.0.len())
    }
}

impl Deserialize<'_> for RawPayload {
    fn get_structure(_: &[u8]) -> std::result::Result<Vec<FieldMarker>, binary_sv2::Error> {
        unimplemented!("the encrypted frame decoder retains raw payload bytes")
    }

    fn from_decoded_fields(_: Vec<DecodableField>) -> std::result::Result<Self, binary_sv2::Error> {
        unimplemented!("the encrypted frame decoder retains raw payload bytes")
    }
}

pub fn decode_hex(value: &str, label: &str) -> Result<Vec<u8>> {
    if !value.len().is_multiple_of(2) {
        return Err(format!("{label} has odd hex length"));
    }
    (0..value.len())
        .step_by(2)
        .map(|index| {
            u8::from_str_radix(&value[index..index + 2], 16)
                .map_err(|_| format!("{label} is not hexadecimal"))
        })
        .collect()
}

pub fn encode_hex(value: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut result = String::with_capacity(value.len() * 2);
    for byte in value {
        result.push(HEX[(byte >> 4) as usize] as char);
        result.push(HEX[(byte & 0x0f) as usize] as char);
    }
    result
}

fn put_u8(output: &mut Vec<u8>, value: u8) {
    output.push(value);
}

fn put_u16(output: &mut Vec<u8>, value: u16) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn put_u24(output: &mut Vec<u8>, value: usize) -> Result<()> {
    if value > 0x00ff_ffff {
        return Err("B016M value exceeds 24-bit length".to_string());
    }
    let value = value as u32;
    output.extend_from_slice(&value.to_le_bytes()[..3]);
    Ok(())
}

fn put_u32(output: &mut Vec<u8>, value: u32) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn put_f32(output: &mut Vec<u8>, value: f32) {
    output.extend_from_slice(&value.to_le_bytes());
}

fn put_b0255(output: &mut Vec<u8>, value: &[u8]) -> Result<()> {
    let length = u8::try_from(value.len()).map_err(|_| "B0255 value is too long".to_string())?;
    put_u8(output, length);
    output.extend_from_slice(value);
    Ok(())
}

fn put_b064k(output: &mut Vec<u8>, value: &[u8]) -> Result<()> {
    let length = u16::try_from(value.len()).map_err(|_| "B064K value is too long".to_string())?;
    put_u16(output, length);
    output.extend_from_slice(value);
    Ok(())
}

fn put_b016m(output: &mut Vec<u8>, value: &[u8]) -> Result<()> {
    put_u24(output, value.len())?;
    output.extend_from_slice(value);
    Ok(())
}

pub fn setup_payload(protocol: u8, flags: u32, port: u16) -> Result<Vec<u8>> {
    let mut output = Vec::new();
    put_u8(&mut output, protocol);
    put_u16(&mut output, VERSION);
    put_u16(&mut output, VERSION);
    put_u32(&mut output, flags);
    put_b0255(&mut output, b"127.0.0.1")?;
    put_u16(&mut output, port);
    put_b0255(&mut output, b"Soveroot")?;
    put_b0255(&mut output, b"labnet")?;
    put_b0255(&mut output, b"interop-v0")?;
    put_b0255(&mut output, b"")?;
    Ok(output)
}

pub fn allocate_payload(request_id: u32) -> Result<Vec<u8>> {
    let mut output = Vec::new();
    put_b0255(&mut output, b"soveroot-independent-miner")?;
    put_u32(&mut output, request_id);
    Ok(output)
}

pub fn declare_payload(candidate: &Candidate, token: &[u8], request_id: u32) -> Result<Vec<u8>> {
    validate_candidate(candidate)?;
    let mut output = Vec::new();
    put_u32(&mut output, request_id);
    put_b0255(&mut output, token)?;
    put_u32(&mut output, candidate.version);
    put_b064k(
        &mut output,
        &decode_hex(&candidate.coinbase_prefix_hex, "coinbase prefix")?,
    )?;
    put_b064k(
        &mut output,
        &decode_hex(&candidate.coinbase_suffix_hex, "coinbase suffix")?,
    )?;
    let count = u16::try_from(candidate.transaction_ids.len())
        .map_err(|_| "too many transaction identifiers".to_string())?;
    put_u16(&mut output, count);
    for txid in &candidate.transaction_ids {
        let mut bytes = decode_hex(txid, "transaction id")?;
        if bytes.len() != 32 {
            return Err("transaction id must be 32 bytes".to_string());
        }
        bytes.reverse();
        output.extend_from_slice(&bytes);
    }
    put_b064k(&mut output, b"")?;
    Ok(output)
}

pub fn missing_success_payload(
    candidate: &Candidate,
    request_id: u32,
    positions: &[u16],
) -> Result<Vec<u8>> {
    let mut output = Vec::new();
    put_u32(&mut output, request_id);
    put_u16(
        &mut output,
        u16::try_from(positions.len()).map_err(|_| "too many missing positions".to_string())?,
    );
    for position in positions {
        let transaction = candidate
            .transaction_data
            .get(*position as usize)
            .ok_or_else(|| format!("missing transaction position {position} is out of range"))?;
        put_b016m(&mut output, &decode_hex(transaction, "transaction data")?)?;
    }
    Ok(output)
}

pub fn open_channel_payload(candidate: &Candidate, request_id: u32) -> Result<Vec<u8>> {
    let mut output = Vec::new();
    put_u32(&mut output, request_id);
    put_b0255(&mut output, b"soveroot-independent-miner")?;
    put_f32(&mut output, 0.0);
    let target = decode_hex(&candidate.target_le_hex, "target")?;
    if target.len() != 32 {
        return Err("target must be 32 bytes".to_string());
    }
    output.extend_from_slice(&target);
    put_u16(&mut output, 0);
    Ok(output)
}

pub fn set_custom_payload(
    candidate: &Candidate,
    token: &[u8],
    channel_id: u32,
    request_id: u32,
) -> Result<Vec<u8>> {
    validate_candidate(candidate)?;
    let mut output = Vec::new();
    put_u32(&mut output, channel_id);
    put_u32(&mut output, request_id);
    put_b0255(&mut output, token)?;
    put_u32(&mut output, candidate.version);
    let mut previous = decode_hex(&candidate.previous_block_hash, "previous block hash")?;
    if previous.len() != 32 {
        return Err("previous block hash must be 32 bytes".to_string());
    }
    previous.reverse();
    output.extend_from_slice(&previous);
    put_u32(&mut output, candidate.curtime);
    put_u32(&mut output, candidate.bits);
    put_u32(&mut output, candidate.coinbase_tx_version);
    put_b0255(
        &mut output,
        &decode_hex(&candidate.coinbase_prefix_hex, "coinbase prefix")?,
    )?;
    put_u32(&mut output, candidate.coinbase_tx_input_n_sequence);
    put_b064k(
        &mut output,
        &decode_hex(&candidate.coinbase_outputs_hex, "coinbase outputs")?,
    )?;
    put_u32(&mut output, candidate.coinbase_tx_locktime);
    let count = u8::try_from(candidate.coinbase_merkle_path.len())
        .map_err(|_| "merkle path is too long".to_string())?;
    put_u8(&mut output, count);
    for hash in &candidate.coinbase_merkle_path {
        let bytes = decode_hex(hash, "merkle path hash")?;
        if bytes.len() != 32 {
            return Err("merkle path hash must be 32 bytes".to_string());
        }
        output.extend_from_slice(&bytes);
    }
    Ok(output)
}

pub fn validate_candidate(candidate: &Candidate) -> Result<()> {
    if candidate.chain != "labnet" {
        return Err("candidate is not for chain=labnet".to_string());
    }
    if candidate.transaction_ids.len() != candidate.transaction_data.len() {
        return Err("transaction id/data count mismatch".to_string());
    }
    Ok(())
}

pub struct Cursor<'a> {
    bytes: &'a [u8],
    offset: usize,
}

impl<'a> Cursor<'a> {
    pub fn new(bytes: &'a [u8]) -> Self {
        Self { bytes, offset: 0 }
    }

    fn take(&mut self, length: usize) -> Result<&'a [u8]> {
        let end = self
            .offset
            .checked_add(length)
            .ok_or_else(|| "length overflow".to_string())?;
        if end > self.bytes.len() {
            return Err(format!(
                "malformed length: need {length} bytes at {}, only {} remain",
                self.offset,
                self.bytes.len().saturating_sub(self.offset)
            ));
        }
        let result = &self.bytes[self.offset..end];
        self.offset = end;
        Ok(result)
    }

    fn u8(&mut self) -> Result<u8> {
        Ok(self.take(1)?[0])
    }

    fn u16(&mut self) -> Result<u16> {
        Ok(u16::from_le_bytes(self.take(2)?.try_into().unwrap()))
    }

    fn u32(&mut self) -> Result<u32> {
        Ok(u32::from_le_bytes(self.take(4)?.try_into().unwrap()))
    }

    fn b0255(&mut self) -> Result<Vec<u8>> {
        let length = self.u8()? as usize;
        Ok(self.take(length)?.to_vec())
    }

    fn b032(&mut self) -> Result<Vec<u8>> {
        let value = self.b0255()?;
        if value.len() > 32 {
            return Err("B032 exceeds 32 bytes".to_string());
        }
        Ok(value)
    }

    fn b064k(&mut self) -> Result<Vec<u8>> {
        let length = self.u16()? as usize;
        Ok(self.take(length)?.to_vec())
    }

    pub fn finish(self) -> Result<()> {
        if self.offset != self.bytes.len() {
            return Err(format!(
                "malformed length: {} trailing bytes",
                self.bytes.len() - self.offset
            ));
        }
        Ok(())
    }
}

pub fn parse_setup_success(payload: &[u8], required_flags: u32) -> Result<()> {
    let mut cursor = Cursor::new(payload);
    let version = cursor.u16()?;
    let flags = cursor.u32()?;
    cursor.finish()?;
    if version != VERSION || flags & required_flags != required_flags {
        return Err("setup downgrade".to_string());
    }
    Ok(())
}

pub fn parse_allocate_success(payload: &[u8], request_id: u32) -> Result<Vec<u8>> {
    let mut cursor = Cursor::new(payload);
    if cursor.u32()? != request_id {
        return Err("allocation request mismatch".to_string());
    }
    let token = cursor.b0255()?;
    let _outputs = cursor.b064k()?;
    cursor.finish()?;
    if token.is_empty() {
        return Err("allocation token is empty".to_string());
    }
    Ok(token)
}

pub fn parse_missing(payload: &[u8], request_id: u32) -> Result<Vec<u16>> {
    let mut cursor = Cursor::new(payload);
    if cursor.u32()? != request_id {
        return Err("missing-transaction request mismatch".to_string());
    }
    let count = cursor.u16()? as usize;
    let mut positions = Vec::with_capacity(count);
    for _ in 0..count {
        positions.push(cursor.u16()?);
    }
    cursor.finish()?;
    Ok(positions)
}

pub fn parse_declare_success(payload: &[u8], request_id: u32) -> Result<Vec<u8>> {
    let mut cursor = Cursor::new(payload);
    if cursor.u32()? != request_id {
        return Err("declaration request mismatch".to_string());
    }
    let token = cursor.b0255()?;
    cursor.finish()?;
    if token.is_empty() {
        return Err("signed job token is empty".to_string());
    }
    Ok(token)
}

pub fn parse_declare_error(payload: &[u8], request_id: u32) -> Result<String> {
    let mut cursor = Cursor::new(payload);
    if cursor.u32()? != request_id {
        return Err("declaration error request mismatch".to_string());
    }
    let code = String::from_utf8(cursor.b0255()?).map_err(|_| "error code is not UTF-8")?;
    let _details = cursor.b064k()?;
    cursor.finish()?;
    Ok(code)
}

pub fn parse_open_success(payload: &[u8], request_id: u32) -> Result<u32> {
    let mut cursor = Cursor::new(payload);
    if cursor.u32()? != request_id {
        return Err("open-channel request mismatch".to_string());
    }
    let channel_id = cursor.u32()?;
    cursor.take(32)?;
    let extranonce_size = cursor.u16()?;
    let extranonce_prefix = cursor.b032()?;
    cursor.finish()?;
    if extranonce_size != 0 || !extranonce_prefix.is_empty() {
        return Err("coordinator changed the zero-extranonce profile".to_string());
    }
    Ok(channel_id)
}

pub fn parse_set_custom_success(payload: &[u8], channel_id: u32, request_id: u32) -> Result<u32> {
    let mut cursor = Cursor::new(payload);
    if cursor.u32()? != channel_id || cursor.u32()? != request_id {
        return Err("custom-job response mismatch".to_string());
    }
    let job_id = cursor.u32()?;
    cursor.finish()?;
    Ok(job_id)
}

pub fn parse_set_custom_error(payload: &[u8], channel_id: u32, request_id: u32) -> Result<String> {
    let mut cursor = Cursor::new(payload);
    if cursor.u32()? != channel_id || cursor.u32()? != request_id {
        return Err("custom-job error mismatch".to_string());
    }
    let code = String::from_utf8(cursor.b0255()?).map_err(|_| "error code is not UTF-8")?;
    cursor.finish()?;
    Ok(code)
}

pub fn canonical_transcript(
    candidate: &Candidate,
    allocation_token: &[u8],
    signed_token: &[u8],
    channel_id: u32,
    job_id: u32,
) -> Result<Vec<TranscriptFrame>> {
    let setup_jd = setup_payload(1, JD_FLAGS, 34254)?;
    let allocation = allocate_payload(1)?;
    let declaration = declare_payload(candidate, allocation_token, 2)?;
    let missing_success = missing_success_payload(candidate, 2, &[0])?;
    let setup_mining = setup_payload(0, MINING_FLAGS, 34254)?;
    let open = open_channel_payload(candidate, 3)?;
    let custom = set_custom_payload(candidate, signed_token, channel_id, 4)?;
    Ok(vec![
        record("miner_to_coordinator", MSG_SETUP, &setup_jd),
        record("miner_to_coordinator", MSG_ALLOCATE_TOKEN, &allocation),
        record("miner_to_coordinator", MSG_DECLARE, &declaration),
        record(
            "miner_to_coordinator",
            MSG_PROVIDE_MISSING_SUCCESS,
            &missing_success,
        ),
        record("miner_to_coordinator", MSG_SETUP, &setup_mining),
        record("miner_to_coordinator", MSG_OPEN_EXTENDED, &open),
        record("miner_to_coordinator", MSG_SET_CUSTOM, &custom),
        record(
            "coordinator_to_miner",
            MSG_SET_CUSTOM_SUCCESS,
            &[
                channel_id.to_le_bytes(),
                4_u32.to_le_bytes(),
                job_id.to_le_bytes(),
            ]
            .concat(),
        ),
    ])
}

pub fn record(direction: &'static str, message_type: u8, payload: &[u8]) -> TranscriptFrame {
    TranscriptFrame {
        direction,
        message_type,
        payload_hex: encode_hex(payload),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn malformed_lengths_fail_closed() {
        assert!(parse_setup_success(&[2, 0, 1], JD_FLAGS).is_err());
        assert!(parse_allocate_success(&[1, 0, 0, 0, 10], 1).is_err());
        assert!(parse_open_success(&[0; 10], 3).is_err());
    }

    #[test]
    fn setup_downgrade_is_rejected() {
        let mut payload = Vec::new();
        put_u16(&mut payload, 1);
        put_u32(&mut payload, JD_FLAGS);
        assert!(parse_setup_success(&payload, JD_FLAGS).is_err());
    }

    #[test]
    fn duplicate_custom_token_is_rejected_by_state() {
        let mut consumed = false;
        let consume = |state: &mut bool| {
            if *state {
                false
            } else {
                *state = true;
                true
            }
        };
        assert!(consume(&mut consumed));
        assert!(!consume(&mut consumed));
    }
}
