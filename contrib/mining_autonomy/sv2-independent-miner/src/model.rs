use serde::{Deserialize, Serialize};

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct Candidate {
    pub chain: String,
    pub height: u64,
    pub previous_block_hash: String,
    pub version: u32,
    pub bits: u32,
    pub curtime: u32,
    pub coinbase_value: u64,
    pub payout_script_hex: String,
    pub coinbase_tx_version: u32,
    pub coinbase_prefix_hex: String,
    pub coinbase_suffix_hex: String,
    pub coinbase_tx_hex: String,
    pub coinbase_outputs_hex: String,
    pub coinbase_tx_input_n_sequence: u32,
    pub coinbase_tx_locktime: u32,
    pub transaction_ids: Vec<String>,
    pub transaction_data: Vec<String>,
    pub coinbase_merkle_path: Vec<String>,
    pub merkle_root_internal_hex: String,
    pub target_le_hex: String,
    pub template_commitment_sha256: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct ExpectedBlock {
    pub nonce: u32,
    pub hash: String,
    pub header_hex: String,
    pub block_hex: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct NegativeVector {
    pub name: String,
    pub expected: String,
}

#[derive(Clone, Debug, Deserialize)]
pub struct InteropFixture {
    pub format: String,
    pub profile: String,
    pub authority_public_key: String,
    pub allocation_token_hex: String,
    pub signed_token_hex: String,
    pub channel_id: u32,
    pub job_id: u32,
    pub candidate: Candidate,
    pub expected_block: ExpectedBlock,
    pub negative_vectors: Vec<NegativeVector>,
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct TranscriptFrame {
    pub direction: &'static str,
    pub message_type: u8,
    pub payload_hex: String,
}

#[derive(Clone, Debug, Serialize, PartialEq, Eq)]
pub struct AuthTranscript {
    pub noise_pattern: &'static str,
    pub authority_public_key: String,
    pub coordinator_authenticated: bool,
    pub job_declaration_version: u16,
    pub job_declaration_flags: u32,
    pub mining_version: u16,
    pub mining_flags: u32,
}
