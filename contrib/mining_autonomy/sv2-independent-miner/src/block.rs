use crate::{
    model::Candidate,
    wire::{decode_hex, encode_hex, Result},
};
use serde::Serialize;
use serde_json::Value;
use sha2::{Digest, Sha256};

#[derive(Clone, Debug)]
pub struct Coinbase {
    pub txid_hash: [u8; 32],
    pub block_bytes: Vec<u8>,
    pub declaration_prefix: Vec<u8>,
    pub declaration_suffix: Vec<u8>,
    pub serialized_outputs: Vec<u8>,
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct SolvedBlock {
    pub nonce: u32,
    pub hash: String,
    pub header_hex: String,
    pub block_hex: String,
}

pub fn hash256(bytes: &[u8]) -> [u8; 32] {
    let first = Sha256::digest(bytes);
    Sha256::digest(&first).into()
}

pub fn encode_varint(value: u64) -> Vec<u8> {
    match value {
        0..=0xfc => vec![value as u8],
        0xfd..=0xffff => {
            let mut output = vec![0xfd];
            output.extend_from_slice(&(value as u16).to_le_bytes());
            output
        }
        0x1_0000..=0xffff_ffff => {
            let mut output = vec![0xfe];
            output.extend_from_slice(&(value as u32).to_le_bytes());
            output
        }
        _ => {
            let mut output = vec![0xff];
            output.extend_from_slice(&value.to_le_bytes());
            output
        }
    }
}

fn script_number(mut value: u64) -> Vec<u8> {
    if value == 0 {
        return Vec::new();
    }
    let mut output = Vec::new();
    while value != 0 {
        output.push((value & 0xff) as u8);
        value >>= 8;
    }
    if output.last().is_some_and(|byte| byte & 0x80 != 0) {
        output.push(0);
    }
    output
}

fn push_data(bytes: &[u8]) -> Result<Vec<u8>> {
    let mut output = Vec::new();
    if bytes.len() <= 75 {
        output.push(bytes.len() as u8);
    } else if bytes.len() <= 255 {
        output.extend_from_slice(&[0x4c, bytes.len() as u8]);
    } else {
        return Err("coinbase pushed data exceeds 255 bytes".to_string());
    }
    output.extend_from_slice(bytes);
    Ok(output)
}

fn encoded_height(height: u64) -> Result<Vec<u8>> {
    if height == 0 {
        return Ok(vec![0]);
    }
    if height <= 16 {
        return Ok(vec![0x50 + height as u8]);
    }
    push_data(&script_number(height))
}

fn serialized_outputs(outputs: &[(u64, Vec<u8>)]) -> Result<Vec<u8>> {
    let mut result = encode_varint(outputs.len() as u64);
    for (value, script) in outputs {
        if *value > i64::MAX as u64 {
            return Err("coinbase value exceeds signed int64".to_string());
        }
        result.extend_from_slice(&(*value as i64).to_le_bytes());
        result.extend_from_slice(&encode_varint(script.len() as u64));
        result.extend_from_slice(script);
    }
    Ok(result)
}

pub fn build_coinbase(
    height: u64,
    value: u64,
    payout_script: &[u8],
    flags: &[u8],
    witness_commitment: Option<&[u8]>,
) -> Result<Coinbase> {
    if payout_script.is_empty() {
        return Err("payout script is empty".to_string());
    }
    let mut script_sig = encoded_height(height)?;
    script_sig.extend_from_slice(flags);
    script_sig.extend_from_slice(&push_data(b"/Soveroot autonomous labnet v0/")?);
    if !(2..=100).contains(&script_sig.len()) {
        return Err("coinbase scriptSig is outside 2..100 bytes".to_string());
    }

    let mut input = vec![0_u8; 32];
    input.extend_from_slice(&u32::MAX.to_le_bytes());
    input.extend_from_slice(&encode_varint(script_sig.len() as u64));
    input.extend_from_slice(&script_sig);
    input.extend_from_slice(&u32::MAX.to_le_bytes());

    let mut outputs = vec![(value, payout_script.to_vec())];
    if let Some(commitment) = witness_commitment {
        if commitment.is_empty() {
            return Err("witness commitment is empty".to_string());
        }
        outputs.push((0, commitment.to_vec()));
    }
    let outputs = serialized_outputs(&outputs)?;

    let mut prefix = 2_u32.to_le_bytes().to_vec();
    prefix.extend_from_slice(&encode_varint(1));
    prefix.extend_from_slice(&[0_u8; 32]);
    prefix.extend_from_slice(&u32::MAX.to_le_bytes());
    prefix.extend_from_slice(&encode_varint(script_sig.len() as u64));
    prefix.extend_from_slice(&script_sig);

    let mut suffix = u32::MAX.to_le_bytes().to_vec();
    suffix.extend_from_slice(&outputs);
    suffix.extend_from_slice(&0_u32.to_le_bytes());
    let mut base = prefix.clone();
    base.extend_from_slice(&suffix);

    let block_bytes = if witness_commitment.is_some() {
        let mut transaction = 2_u32.to_le_bytes().to_vec();
        transaction.extend_from_slice(&[0, 1]);
        transaction.extend_from_slice(&encode_varint(1));
        transaction.extend_from_slice(&input);
        transaction.extend_from_slice(&outputs);
        transaction.extend_from_slice(&[1, 32]);
        transaction.extend_from_slice(&[0_u8; 32]);
        transaction.extend_from_slice(&0_u32.to_le_bytes());
        transaction
    } else {
        base.clone()
    };

    Ok(Coinbase {
        txid_hash: hash256(&base),
        block_bytes,
        declaration_prefix: prefix,
        declaration_suffix: suffix,
        serialized_outputs: outputs,
    })
}

pub fn merkle_root(mut hashes: Vec<[u8; 32]>) -> Result<[u8; 32]> {
    if hashes.is_empty() {
        return Err("block has no coinbase hash".to_string());
    }
    while hashes.len() > 1 {
        if hashes.len() % 2 == 1 {
            hashes.push(*hashes.last().unwrap());
        }
        hashes = hashes
            .chunks_exact(2)
            .map(|pair| {
                let mut input = [0_u8; 64];
                input[..32].copy_from_slice(&pair[0]);
                input[32..].copy_from_slice(&pair[1]);
                hash256(&input)
            })
            .collect();
    }
    Ok(hashes[0])
}

pub fn coinbase_merkle_path(mut hashes: Vec<[u8; 32]>) -> Result<Vec<[u8; 32]>> {
    if hashes.is_empty() {
        return Err("block has no coinbase hash".to_string());
    }
    let mut path = Vec::new();
    while hashes.len() > 1 {
        if hashes.len() % 2 == 1 {
            hashes.push(*hashes.last().unwrap());
        }
        path.push(hashes[1]);
        hashes = hashes
            .chunks_exact(2)
            .map(|pair| {
                let mut input = [0_u8; 64];
                input[..32].copy_from_slice(&pair[0]);
                input[32..].copy_from_slice(&pair[1]);
                hash256(&input)
            })
            .collect();
    }
    Ok(path)
}

pub fn target_from_compact(bits: u32) -> Result<[u8; 32]> {
    let exponent = (bits >> 24) as usize;
    let mantissa = bits & 0x007f_ffff;
    if bits & 0x0080_0000 != 0 || mantissa == 0 {
        return Err("invalid compact target".to_string());
    }
    let value = if exponent <= 3 {
        mantissa >> (8 * (3 - exponent))
    } else {
        mantissa
    };
    let mut target = [0_u8; 32];
    if exponent <= 3 {
        target[..4].copy_from_slice(&value.to_le_bytes());
    } else {
        let offset = exponent - 3;
        if offset + 3 > target.len() {
            return Err("compact target exceeds 256 bits".to_string());
        }
        target[offset..offset + 3].copy_from_slice(&value.to_le_bytes()[..3]);
    }
    Ok(target)
}

fn less_or_equal_little_endian(value: &[u8; 32], target: &[u8; 32]) -> bool {
    for index in (0..32).rev() {
        if value[index] < target[index] {
            return true;
        }
        if value[index] > target[index] {
            return false;
        }
    }
    true
}

pub fn solve_candidate(candidate: &Candidate, max_nonce: u32) -> Result<SolvedBlock> {
    if candidate.chain != "labnet" {
        return Err("refusing to solve a non-labnet candidate".to_string());
    }
    let mut previous = decode_hex(&candidate.previous_block_hash, "previous block hash")?;
    if previous.len() != 32 {
        return Err("previous block hash must be 32 bytes".to_string());
    }
    previous.reverse();
    let merkle = decode_hex(&candidate.merkle_root_internal_hex, "merkle root")?;
    if merkle.len() != 32 {
        return Err("merkle root must be 32 bytes".to_string());
    }
    let target = target_from_compact(candidate.bits)?;
    if encode_hex(&target) != candidate.target_le_hex {
        return Err("candidate target does not match compact bits".to_string());
    }

    let mut prefix = candidate.version.to_le_bytes().to_vec();
    prefix.extend_from_slice(&previous);
    prefix.extend_from_slice(&merkle);
    prefix.extend_from_slice(&candidate.curtime.to_le_bytes());
    prefix.extend_from_slice(&candidate.bits.to_le_bytes());

    for nonce in 0..=max_nonce {
        let mut header = prefix.clone();
        header.extend_from_slice(&nonce.to_le_bytes());
        let digest = hash256(&header);
        if less_or_equal_little_endian(&digest, &target) {
            let mut transactions = vec![decode_hex(
                &candidate.coinbase_tx_hex,
                "coinbase transaction",
            )?];
            for transaction in &candidate.transaction_data {
                transactions.push(decode_hex(transaction, "transaction data")?);
            }
            let mut block = header.clone();
            block.extend_from_slice(&encode_varint(transactions.len() as u64));
            for transaction in transactions {
                block.extend_from_slice(&transaction);
            }
            let mut display_hash = digest;
            display_hash.reverse();
            return Ok(SolvedBlock {
                nonce,
                hash: encode_hex(&display_hash),
                header_hex: encode_hex(&header),
                block_hex: encode_hex(&block),
            });
        }
    }
    Err(format!("no valid nonce found in range 0..={max_nonce}"))
}

pub fn template_commitment(candidate: &Candidate) -> Result<String> {
    let mut value = serde_json::to_value(candidate).map_err(|error| error.to_string())?;
    let object = value
        .as_object_mut()
        .ok_or_else(|| "candidate did not serialize as an object".to_string())?;
    object.remove("template_commitment_sha256");
    let bytes =
        serde_json::to_vec(&Value::Object(object.clone())).map_err(|error| error.to_string())?;
    Ok(encode_hex(&Sha256::digest(&bytes)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::model::InteropFixture;

    fn fixture() -> InteropFixture {
        serde_json::from_str(include_str!("../../vectors/sv2_interoperability_v0.json")).unwrap()
    }

    #[test]
    fn independent_block_matches_canonical_fixture() {
        let fixture = fixture();
        let solved = solve_candidate(&fixture.candidate, 100).unwrap();
        assert_eq!(solved.nonce, fixture.expected_block.nonce);
        assert_eq!(solved.hash, fixture.expected_block.hash);
        assert_eq!(solved.header_hex, fixture.expected_block.header_hex);
        assert_eq!(solved.block_hex, fixture.expected_block.block_hex);
    }

    #[test]
    fn independent_commitment_matches_reference_fixture() {
        let fixture = fixture();
        assert_eq!(
            template_commitment(&fixture.candidate).unwrap(),
            fixture.candidate.template_commitment_sha256
        );
    }

    #[test]
    fn stale_candidate_is_rejected_before_solving() {
        let mut fixture = fixture();
        fixture.candidate.chain = "regtest".to_string();
        assert!(solve_candidate(&fixture.candidate, 100).is_err());
    }
}
