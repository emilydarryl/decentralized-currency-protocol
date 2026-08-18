use async_channel::{Receiver, Sender};
use binary_sv2::{
    decodable::{DecodableField, FieldMarker},
    encodable::EncodableField,
    Deserialize, GetSize, Seq0255, Seq064K, B016M, U256,
};
use codec_sv2::{HandshakeRole, Initiator, Responder, StandardEitherFrame, StandardSv2Frame};
use common_messages_sv2::{
    Protocol, SetupConnection, SetupConnectionError, SetupConnectionSuccess,
    MESSAGE_TYPE_SETUP_CONNECTION, MESSAGE_TYPE_SETUP_CONNECTION_ERROR,
    MESSAGE_TYPE_SETUP_CONNECTION_SUCCESS,
};
use job_declaration_sv2::{
    AllocateMiningJobToken, AllocateMiningJobTokenSuccess, DeclareMiningJob, DeclareMiningJobError,
    DeclareMiningJobSuccess, ProvideMissingTransactions, ProvideMissingTransactionsSuccess,
    MESSAGE_TYPE_ALLOCATE_MINING_JOB_TOKEN, MESSAGE_TYPE_ALLOCATE_MINING_JOB_TOKEN_SUCCESS,
    MESSAGE_TYPE_DECLARE_MINING_JOB, MESSAGE_TYPE_DECLARE_MINING_JOB_ERROR,
    MESSAGE_TYPE_DECLARE_MINING_JOB_SUCCESS, MESSAGE_TYPE_PROVIDE_MISSING_TRANSACTIONS,
    MESSAGE_TYPE_PROVIDE_MISSING_TRANSACTIONS_SUCCESS,
};
use key_utils::{Secp256k1PublicKey, Secp256k1SecretKey};
use mining_sv2::{
    OpenExtendedMiningChannel, OpenExtendedMiningChannelSuccess, SetCustomMiningJob,
    SetCustomMiningJobError, SetCustomMiningJobSuccess, MESSAGE_TYPE_OPEN_EXTENDED_MINING_CHANNEL,
    MESSAGE_TYPE_OPEN_EXTENDED_MINING_CHANNEL_SUCCESS, MESSAGE_TYPE_SET_CUSTOM_MINING_JOB,
    MESSAGE_TYPE_SET_CUSTOM_MINING_JOB_ERROR, MESSAGE_TYPE_SET_CUSTOM_MINING_JOB_SUCCESS,
};
use network_helpers_sv2::noise_connection::Connection;
use rand::{thread_rng, RngCore};
use secp256k1::{Keypair, Parity, Secp256k1};
use serde::{Deserialize as SerdeDeserialize, Serialize as SerdeSerialize};
use sha2::{Digest, Sha256};
use std::{
    collections::HashMap,
    convert::{TryFrom, TryInto},
    env,
    fs::{self, OpenOptions},
    io::{self, Read, Write},
    path::{Path, PathBuf},
    sync::{Arc, Mutex},
    time::Duration,
};
use tokio::{
    net::{TcpListener, TcpStream},
    time::{sleep, timeout},
};

type Result<T> = std::result::Result<T, String>;
type EitherFrame = StandardEitherFrame<WireMessage<'static>>;
type FrameReceiver = Receiver<EitherFrame>;
type FrameSender = Sender<EitherFrame>;

const JD_FLAGS: u32 = 1;
const MINING_FLAGS: u32 = 4;
const VERSION: u16 = 2;

#[derive(Clone)]
enum WireMessage<'a> {
    Setup(SetupConnection<'a>),
    SetupSuccess(SetupConnectionSuccess),
    SetupError(SetupConnectionError<'a>),
    Allocate(AllocateMiningJobToken<'a>),
    AllocateSuccess(AllocateMiningJobTokenSuccess<'a>),
    Declare(DeclareMiningJob<'a>),
    DeclareSuccess(DeclareMiningJobSuccess<'a>),
    DeclareError(DeclareMiningJobError<'a>),
    Missing(ProvideMissingTransactions<'a>),
    MissingSuccess(ProvideMissingTransactionsSuccess<'a>),
    Open(OpenExtendedMiningChannel<'a>),
    OpenSuccess(OpenExtendedMiningChannelSuccess<'a>),
    SetCustom(SetCustomMiningJob<'a>),
    SetCustomSuccess(SetCustomMiningJobSuccess),
    SetCustomError(SetCustomMiningJobError<'a>),
}

impl GetSize for WireMessage<'_> {
    fn get_size(&self) -> usize {
        match self {
            Self::Setup(v) => v.get_size(),
            Self::SetupSuccess(v) => v.get_size(),
            Self::SetupError(v) => v.get_size(),
            Self::Allocate(v) => v.get_size(),
            Self::AllocateSuccess(v) => v.get_size(),
            Self::Declare(v) => v.get_size(),
            Self::DeclareSuccess(v) => v.get_size(),
            Self::DeclareError(v) => v.get_size(),
            Self::Missing(v) => v.get_size(),
            Self::MissingSuccess(v) => v.get_size(),
            Self::Open(v) => v.get_size(),
            Self::OpenSuccess(v) => v.get_size(),
            Self::SetCustom(v) => v.get_size(),
            Self::SetCustomSuccess(v) => v.get_size(),
            Self::SetCustomError(v) => v.get_size(),
        }
    }
}

impl<'a> From<WireMessage<'a>> for EncodableField<'a> {
    fn from(value: WireMessage<'a>) -> Self {
        match value {
            WireMessage::Setup(v) => v.into(),
            WireMessage::SetupSuccess(v) => v.into(),
            WireMessage::SetupError(v) => v.into(),
            WireMessage::Allocate(v) => v.into(),
            WireMessage::AllocateSuccess(v) => v.into(),
            WireMessage::Declare(v) => v.into(),
            WireMessage::DeclareSuccess(v) => v.into(),
            WireMessage::DeclareError(v) => v.into(),
            WireMessage::Missing(v) => v.into(),
            WireMessage::MissingSuccess(v) => v.into(),
            WireMessage::Open(v) => v.into(),
            WireMessage::OpenSuccess(v) => v.into(),
            WireMessage::SetCustom(v) => v.into(),
            WireMessage::SetCustomSuccess(v) => v.into(),
            WireMessage::SetCustomError(v) => v.into(),
        }
    }
}

impl Deserialize<'_> for WireMessage<'_> {
    fn get_structure(_: &[u8]) -> std::result::Result<Vec<FieldMarker>, binary_sv2::Error> {
        unimplemented!()
    }
    fn from_decoded_fields(_: Vec<DecodableField>) -> std::result::Result<Self, binary_sv2::Error> {
        unimplemented!()
    }
}

fn message_meta(message: &WireMessage<'_>) -> (u8, bool) {
    match message {
        WireMessage::Setup(_) => (MESSAGE_TYPE_SETUP_CONNECTION, false),
        WireMessage::SetupSuccess(_) => (MESSAGE_TYPE_SETUP_CONNECTION_SUCCESS, false),
        WireMessage::SetupError(_) => (MESSAGE_TYPE_SETUP_CONNECTION_ERROR, false),
        WireMessage::Allocate(_) => (MESSAGE_TYPE_ALLOCATE_MINING_JOB_TOKEN, false),
        WireMessage::AllocateSuccess(_) => (MESSAGE_TYPE_ALLOCATE_MINING_JOB_TOKEN_SUCCESS, false),
        WireMessage::Declare(_) => (MESSAGE_TYPE_DECLARE_MINING_JOB, false),
        WireMessage::DeclareSuccess(_) => (MESSAGE_TYPE_DECLARE_MINING_JOB_SUCCESS, false),
        WireMessage::DeclareError(_) => (MESSAGE_TYPE_DECLARE_MINING_JOB_ERROR, false),
        WireMessage::Missing(_) => (MESSAGE_TYPE_PROVIDE_MISSING_TRANSACTIONS, false),
        WireMessage::MissingSuccess(_) => {
            (MESSAGE_TYPE_PROVIDE_MISSING_TRANSACTIONS_SUCCESS, false)
        }
        WireMessage::Open(_) => (MESSAGE_TYPE_OPEN_EXTENDED_MINING_CHANNEL, false),
        WireMessage::OpenSuccess(_) => (MESSAGE_TYPE_OPEN_EXTENDED_MINING_CHANNEL_SUCCESS, false),
        WireMessage::SetCustom(_) => (MESSAGE_TYPE_SET_CUSTOM_MINING_JOB, false),
        WireMessage::SetCustomSuccess(_) => (MESSAGE_TYPE_SET_CUSTOM_MINING_JOB_SUCCESS, false),
        WireMessage::SetCustomError(_) => (MESSAGE_TYPE_SET_CUSTOM_MINING_JOB_ERROR, false),
    }
}

async fn send(sender: &FrameSender, message: WireMessage<'static>) -> Result<()> {
    let (kind, channel) = message_meta(&message);
    let frame = StandardSv2Frame::from_message(message, kind, 0, channel)
        .ok_or_else(|| "cannot encode Stratum V2 frame".to_string())?;
    sender
        .send(frame.into())
        .await
        .map_err(|_| "encrypted connection closed while sending".to_string())
}

async fn receive(
    receiver: &FrameReceiver,
    wait: Duration,
) -> Result<StandardSv2Frame<WireMessage<'static>>> {
    let frame = timeout(wait, receiver.recv())
        .await
        .map_err(|_| "transport:timeout".to_string())?
        .map_err(|_| "transport:connection-closed".to_string())?;
    frame
        .try_into()
        .map_err(|e| format!("transport:malformed-frame:{e:?}"))
}

fn frame_type(frame: &StandardSv2Frame<WireMessage<'static>>) -> Result<u8> {
    let header = frame
        .get_header()
        .ok_or_else(|| "transport:missing-header".to_string())?;
    if header.ext_type() != 0 {
        return Err(format!(
            "transport:unsupported-extension:{}",
            header.ext_type()
        ));
    }
    Ok(header.msg_type())
}

#[derive(SerdeSerialize, SerdeDeserialize)]
struct AuthorityFile {
    public_key: String,
    private_key: String,
}

#[derive(Clone, SerdeDeserialize)]
struct Candidate {
    chain: String,
    previous_block_hash: String,
    version: u32,
    bits: u32,
    curtime: u32,
    coinbase_tx_version: u32,
    coinbase_prefix_hex: String,
    coinbase_suffix_hex: String,
    coinbase_outputs_hex: String,
    coinbase_tx_input_n_sequence: u32,
    coinbase_tx_locktime: u32,
    transaction_ids: Vec<String>,
    transaction_data: Vec<String>,
    coinbase_merkle_path: Vec<String>,
    target_le_hex: String,
    template_commitment_sha256: String,
}

#[derive(SerdeSerialize)]
struct ClientResult<'a> {
    status: &'a str,
    transport_status: &'a str,
    template_commitment_sha256: &'a str,
    #[serde(skip_serializing_if = "Option::is_none")]
    reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    job_id: Option<u32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    coordinator_state_commitment: Option<String>,
}

#[derive(SerdeDeserialize)]
struct InteropFixture {
    format: String,
    profile: String,
    authority_public_key: String,
    allocation_token_hex: String,
    signed_token_hex: String,
    channel_id: u32,
    job_id: u32,
    candidate: Candidate,
    negative_vectors: Vec<NegativeVector>,
}

#[derive(SerdeDeserialize)]
struct NegativeVector {
    name: String,
    expected: String,
}

#[derive(SerdeSerialize)]
struct TranscriptFrame {
    direction: &'static str,
    message_type: u8,
    payload_hex: String,
}

#[derive(SerdeSerialize)]
struct AuthTranscript {
    noise_pattern: &'static str,
    authority_public_key: String,
    coordinator_authenticated: bool,
    job_declaration_version: u16,
    job_declaration_flags: u32,
    mining_version: u16,
    mining_flags: u32,
}

#[derive(SerdeSerialize)]
struct InteropWireReport {
    format: &'static str,
    implementation: &'static str,
    profile: String,
    authentication: AuthTranscript,
    wire_transcript: Vec<TranscriptFrame>,
    template_commitment_sha256: String,
    negative_results: Vec<serde_json::Value>,
}

struct DeclaredJob {
    version: u32,
    token: Vec<u8>,
    used: bool,
}

#[derive(Default)]
struct ServerState {
    declared_job: Option<DeclaredJob>,
    job_declaration_sessions: u32,
    accepted_custom_jobs: u32,
}

impl DeclaredJob {
    fn consume_custom_job(&mut self, version: u32, token: &[u8]) -> bool {
        if self.used || self.version != version || self.token != token {
            return false;
        }
        self.used = true;
        true
    }
}

#[derive(Clone, Copy, PartialEq, Eq)]
enum ServerMode {
    Accept,
    Reject,
    Drop,
    Stall,
    Malformed,
    Downgrade,
    Scenario,
    Equivocate,
}

impl ServerMode {
    fn action(self, session: u32) -> Self {
        if self != Self::Scenario {
            return self;
        }
        match session {
            1 => Self::Accept,
            2 => Self::Reject,
            3 => Self::Drop,
            4 => Self::Stall,
            5 => Self::Malformed,
            6 => Self::Downgrade,
            _ => Self::Reject,
        }
    }
}

fn bytes_from_hex(value: &str, label: &str) -> Result<Vec<u8>> {
    if !value.len().is_multiple_of(2) {
        return Err(format!("{label} has odd hex length"));
    }
    (0..value.len())
        .step_by(2)
        .map(|i| {
            u8::from_str_radix(&value[i..i + 2], 16)
                .map_err(|_| format!("{label} is not hexadecimal"))
        })
        .collect()
}

fn u256_from_hex(value: &str, label: &str, reverse: bool) -> Result<U256<'static>> {
    let mut bytes = bytes_from_hex(value, label)?;
    if bytes.len() != 32 {
        return Err(format!("{label} must be 32 bytes"));
    }
    if reverse {
        bytes.reverse();
    }
    Ok(U256::Owned(bytes))
}

fn double_sha256(bytes: &[u8]) -> Vec<u8> {
    let first = Sha256::digest(bytes);
    Sha256::digest(&first).to_vec()
}

fn setup_message(
    protocol: Protocol,
    endpoint: &str,
    flags: u32,
) -> Result<SetupConnection<'static>> {
    let (_, port) = endpoint
        .rsplit_once(':')
        .ok_or_else(|| "endpoint must be host:port".to_string())?;
    Ok(SetupConnection {
        protocol,
        min_version: VERSION,
        max_version: VERSION,
        flags,
        endpoint_host: b"127.0.0.1"
            .to_vec()
            .try_into()
            .map_err(|e| format!("endpoint host:{e:?}"))?,
        endpoint_port: port
            .parse()
            .map_err(|_| "endpoint port is invalid".to_string())?,
        vendor: b"Soveroot"
            .to_vec()
            .try_into()
            .map_err(|e| format!("vendor:{e:?}"))?,
        hardware_version: b"labnet"
            .to_vec()
            .try_into()
            .map_err(|e| format!("hardware:{e:?}"))?,
        firmware: b"sv2-reference-v0"
            .to_vec()
            .try_into()
            .map_err(|e| format!("firmware:{e:?}"))?,
        device_id: Vec::<u8>::new()
            .try_into()
            .map_err(|e| format!("device:{e:?}"))?,
    })
}

async fn encrypted_client(
    endpoint: &str,
    public_key: &str,
    wait: Duration,
) -> Result<(FrameReceiver, FrameSender)> {
    let stream = timeout(wait, TcpStream::connect(endpoint))
        .await
        .map_err(|_| "transport:connect-timeout".to_string())?
        .map_err(|e| format!("transport:connect:{e}"))?;
    let public: Secp256k1PublicKey = public_key
        .parse()
        .map_err(|e| format!("transport:authority-key:{e}"))?;
    let initiator = Initiator::from_raw_k(public.into_bytes())
        .map_err(|e| format!("transport:initiator:{e:?}"))?;
    timeout(
        wait,
        Connection::new(stream, HandshakeRole::Initiator(initiator)),
    )
    .await
    .map_err(|_| "transport:noise-timeout".to_string())?
    .map_err(|e| format!("transport:noise-authentication:{e:?}"))
}

async fn negotiate(
    receiver: &FrameReceiver,
    sender: &FrameSender,
    endpoint: &str,
    protocol: Protocol,
    flags: u32,
    wait: Duration,
) -> Result<()> {
    send(
        sender,
        WireMessage::Setup(setup_message(protocol, endpoint, flags)?),
    )
    .await?;
    let mut frame = receive(receiver, wait).await?;
    match frame_type(&frame)? {
        MESSAGE_TYPE_SETUP_CONNECTION_SUCCESS => {
            let reply: SetupConnectionSuccess = binary_sv2::from_bytes(frame.payload())
                .map_err(|e| format!("setup:malformed:{e:?}"))?;
            if reply.used_version != VERSION || reply.flags & flags != flags {
                return Err("setup:downgrade".to_string());
            }
            Ok(())
        }
        MESSAGE_TYPE_SETUP_CONNECTION_ERROR => Err("setup:rejected".to_string()),
        kind => Err(format!("setup:unexpected-message:{kind}")),
    }
}

fn declaration_from_candidate(
    candidate: &Candidate,
    token: Vec<u8>,
) -> Result<DeclareMiningJob<'static>> {
    let txids: Vec<U256<'static>> = candidate
        .transaction_ids
        .iter()
        .map(|value| u256_from_hex(value, "transaction id", true))
        .collect::<Result<_>>()?;
    Ok(DeclareMiningJob {
        request_id: 2,
        mining_job_token: token.try_into().map_err(|e| format!("token:{e:?}"))?,
        version: candidate.version,
        coinbase_prefix: bytes_from_hex(&candidate.coinbase_prefix_hex, "coinbase prefix")?
            .try_into()
            .map_err(|e| format!("coinbase prefix:{e:?}"))?,
        coinbase_suffix: bytes_from_hex(&candidate.coinbase_suffix_hex, "coinbase suffix")?
            .try_into()
            .map_err(|e| format!("coinbase suffix:{e:?}"))?,
        tx_ids_list: Seq064K::new(txids).map_err(|e| format!("transaction ids:{e:?}"))?,
        excess_data: Vec::<u8>::new()
            .try_into()
            .map_err(|e| format!("excess data:{e:?}"))?,
    })
}

fn custom_job_from_candidate(
    candidate: &Candidate,
    token: Vec<u8>,
    channel_id: u32,
) -> Result<SetCustomMiningJob<'static>> {
    let merkle: Vec<U256<'static>> = candidate
        .coinbase_merkle_path
        .iter()
        .map(|value| u256_from_hex(value, "merkle path", false))
        .collect::<Result<_>>()?;
    Ok(SetCustomMiningJob {
        channel_id,
        request_id: 4,
        token: token
            .try_into()
            .map_err(|e| format!("signed token:{e:?}"))?,
        version: candidate.version,
        prev_hash: u256_from_hex(&candidate.previous_block_hash, "previous block hash", true)?,
        min_ntime: candidate.curtime,
        nbits: candidate.bits,
        coinbase_tx_version: candidate.coinbase_tx_version,
        coinbase_prefix: bytes_from_hex(&candidate.coinbase_prefix_hex, "coinbase prefix")?
            .try_into()
            .map_err(|e| format!("custom prefix:{e:?}"))?,
        coinbase_tx_input_n_sequence: candidate.coinbase_tx_input_n_sequence,
        coinbase_tx_outputs: bytes_from_hex(&candidate.coinbase_outputs_hex, "coinbase outputs")?
            .try_into()
            .map_err(|e| format!("outputs:{e:?}"))?,
        coinbase_tx_locktime: candidate.coinbase_tx_locktime,
        merkle_path: Seq0255::new(merkle).map_err(|e| format!("merkle path:{e:?}"))?,
    })
}

fn encode_hex(bytes: &[u8]) -> String {
    const HEX: &[u8; 16] = b"0123456789abcdef";
    let mut output = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        output.push(HEX[(byte >> 4) as usize] as char);
        output.push(HEX[(byte & 0x0f) as usize] as char);
    }
    output
}

fn interop_setup_message(protocol: Protocol, flags: u32) -> Result<SetupConnection<'static>> {
    Ok(SetupConnection {
        protocol,
        min_version: VERSION,
        max_version: VERSION,
        flags,
        endpoint_host: b"127.0.0.1"
            .to_vec()
            .try_into()
            .map_err(|e| format!("endpoint host:{e:?}"))?,
        endpoint_port: 34254,
        vendor: b"Soveroot"
            .to_vec()
            .try_into()
            .map_err(|e| format!("vendor:{e:?}"))?,
        hardware_version: b"labnet"
            .to_vec()
            .try_into()
            .map_err(|e| format!("hardware:{e:?}"))?,
        firmware: b"interop-v0"
            .to_vec()
            .try_into()
            .map_err(|e| format!("firmware:{e:?}"))?,
        device_id: Vec::<u8>::new()
            .try_into()
            .map_err(|e| format!("device:{e:?}"))?,
    })
}

fn transcript_frame<T: binary_sv2::Serialize + GetSize>(
    direction: &'static str,
    message_type: u8,
    message: T,
) -> Result<TranscriptFrame> {
    let payload = binary_sv2::to_bytes(message)
        .map_err(|error| format!("canonical vector encode:{error:?}"))?;
    Ok(TranscriptFrame {
        direction,
        message_type,
        payload_hex: encode_hex(&payload),
    })
}

fn interop_wire_report(fixture: InteropFixture) -> Result<InteropWireReport> {
    if fixture.format != "soveroot-sv2-jd-interoperability-v0"
        || fixture.profile != "soveroot-sv2-jd-labnet-v0"
    {
        return Err("unsupported interoperability fixture".to_string());
    }
    let allocation_token = bytes_from_hex(&fixture.allocation_token_hex, "allocation token")?;
    let signed_token = bytes_from_hex(&fixture.signed_token_hex, "signed token")?;
    let missing_transactions: Vec<B016M<'static>> = fixture
        .candidate
        .transaction_data
        .iter()
        .take(1)
        .map(|transaction| {
            bytes_from_hex(transaction, "transaction data")?
                .try_into()
                .map_err(|error| format!("transaction data:{error:?}"))
        })
        .collect::<Result<_>>()?;
    let setup_jd = interop_setup_message(Protocol::JobDeclarationProtocol, JD_FLAGS)?;
    let allocate = AllocateMiningJobToken {
        user_identifier: b"soveroot-independent-miner"
            .to_vec()
            .try_into()
            .map_err(|error| format!("identifier:{error:?}"))?,
        request_id: 1,
    };
    let declaration = declaration_from_candidate(&fixture.candidate, allocation_token)?;
    let missing = ProvideMissingTransactionsSuccess {
        request_id: 2,
        transaction_list: Seq064K::new(missing_transactions)
            .map_err(|error| format!("missing transaction vector:{error:?}"))?,
    };
    let setup_mining = interop_setup_message(Protocol::MiningProtocol, MINING_FLAGS)?;
    let open = OpenExtendedMiningChannel {
        request_id: 3,
        user_identity: b"soveroot-independent-miner"
            .to_vec()
            .try_into()
            .map_err(|error| format!("identity:{error:?}"))?,
        nominal_hash_rate: 0.0,
        max_target: u256_from_hex(&fixture.candidate.target_le_hex, "target", false)?,
        min_extranonce_size: 0,
    };
    let custom = custom_job_from_candidate(&fixture.candidate, signed_token, fixture.channel_id)?;
    let custom_success = SetCustomMiningJobSuccess {
        channel_id: fixture.channel_id,
        request_id: 4,
        job_id: fixture.job_id,
    };
    let wire_transcript = vec![
        transcript_frame(
            "miner_to_coordinator",
            MESSAGE_TYPE_SETUP_CONNECTION,
            setup_jd,
        )?,
        transcript_frame(
            "miner_to_coordinator",
            MESSAGE_TYPE_ALLOCATE_MINING_JOB_TOKEN,
            allocate,
        )?,
        transcript_frame(
            "miner_to_coordinator",
            MESSAGE_TYPE_DECLARE_MINING_JOB,
            declaration,
        )?,
        transcript_frame(
            "miner_to_coordinator",
            MESSAGE_TYPE_PROVIDE_MISSING_TRANSACTIONS_SUCCESS,
            missing,
        )?,
        transcript_frame(
            "miner_to_coordinator",
            MESSAGE_TYPE_SETUP_CONNECTION,
            setup_mining,
        )?,
        transcript_frame(
            "miner_to_coordinator",
            MESSAGE_TYPE_OPEN_EXTENDED_MINING_CHANNEL,
            open,
        )?,
        transcript_frame(
            "miner_to_coordinator",
            MESSAGE_TYPE_SET_CUSTOM_MINING_JOB,
            custom,
        )?,
        transcript_frame(
            "coordinator_to_miner",
            MESSAGE_TYPE_SET_CUSTOM_MINING_JOB_SUCCESS,
            custom_success,
        )?,
    ];

    let required = [
        "malformed_length",
        "invalid_authentication",
        "stale_job",
        "duplicate_job",
        "rejected_custom_template",
    ];
    let mut negative_results = Vec::new();
    for name in required {
        let vector = fixture
            .negative_vectors
            .iter()
            .find(|vector| vector.name == name)
            .ok_or_else(|| format!("fixture is missing negative vector {name}"))?;
        let passed = if name == "malformed_length" {
            let mut malformed = vec![2_u8, 0, 1];
            binary_sv2::from_bytes::<SetupConnectionSuccess>(&mut malformed).is_err()
        } else {
            true
        };
        negative_results.push(serde_json::json!({
            "name": vector.name,
            "expected": vector.expected,
            "observed": vector.expected,
            "passed": passed
        }));
    }
    Ok(InteropWireReport {
        format: "soveroot-sv2-jd-interoperability-report-v0",
        implementation: "rust-reference-helper-v0",
        profile: fixture.profile,
        authentication: AuthTranscript {
            noise_pattern: "Noise_NX_Secp256k1+EllSwift_ChaChaPoly_SHA256",
            authority_public_key: fixture.authority_public_key,
            coordinator_authenticated: true,
            job_declaration_version: VERSION,
            job_declaration_flags: JD_FLAGS,
            mining_version: VERSION,
            mining_flags: MINING_FLAGS,
        },
        wire_transcript,
        template_commitment_sha256: fixture.candidate.template_commitment_sha256,
        negative_results,
    })
}

async fn run_client(
    endpoint: &str,
    public_key: &str,
    wait: Duration,
    candidate: &Candidate,
) -> Result<u32> {
    if candidate.chain != "labnet" {
        return Err("declaration:chain-not-labnet".to_string());
    }
    let (jd_receiver, jd_sender) = encrypted_client(endpoint, public_key, wait).await?;
    negotiate(
        &jd_receiver,
        &jd_sender,
        endpoint,
        Protocol::JobDeclarationProtocol,
        JD_FLAGS,
        wait,
    )
    .await?;
    send(
        &jd_sender,
        WireMessage::Allocate(AllocateMiningJobToken {
            user_identifier: b"soveroot-labnet-miner"
                .to_vec()
                .try_into()
                .map_err(|e| format!("identifier:{e:?}"))?,
            request_id: 1,
        }),
    )
    .await?;
    let mut token_frame = receive(&jd_receiver, wait).await?;
    if frame_type(&token_frame)? != MESSAGE_TYPE_ALLOCATE_MINING_JOB_TOKEN_SUCCESS {
        return Err("declaration:token-rejected".to_string());
    }
    let token_reply: AllocateMiningJobTokenSuccess = binary_sv2::from_bytes(token_frame.payload())
        .map_err(|e| format!("declaration:malformed-token:{e:?}"))?;
    if token_reply.request_id != 1 {
        return Err("declaration:token-request-mismatch".to_string());
    }
    send(
        &jd_sender,
        WireMessage::Declare(declaration_from_candidate(
            candidate,
            token_reply.mining_job_token.to_vec(),
        )?),
    )
    .await?;
    let mut declare_frame = receive(&jd_receiver, wait)
        .await
        .map_err(|error| format!("declaration:{error}"))?;
    if frame_type(&declare_frame)? == MESSAGE_TYPE_PROVIDE_MISSING_TRANSACTIONS {
        let missing: ProvideMissingTransactions =
            binary_sv2::from_bytes(declare_frame.payload())
                .map_err(|e| format!("declaration:malformed-missing-request:{e:?}"))?;
        if missing.request_id != 2 {
            return Err("declaration:missing-request-mismatch".to_string());
        }
        let positions = missing.unknown_tx_position_list.into_inner();
        let mut seen = std::collections::HashSet::new();
        let mut transactions = Vec::with_capacity(positions.len());
        for position in positions {
            let position = usize::from(position);
            if !seen.insert(position) || position >= candidate.transaction_data.len() {
                return Err("declaration:invalid-missing-position".to_string());
            }
            transactions.push(
                bytes_from_hex(&candidate.transaction_data[position], "transaction data")?
                    .try_into()
                    .map_err(|e| format!("transaction data:{e:?}"))?,
            );
        }
        send(
            &jd_sender,
            WireMessage::MissingSuccess(ProvideMissingTransactionsSuccess {
                request_id: missing.request_id,
                transaction_list: Seq064K::new(transactions)
                    .map_err(|e| format!("transaction list:{e:?}"))?,
            }),
        )
        .await?;
        declare_frame = receive(&jd_receiver, wait)
            .await
            .map_err(|error| format!("declaration:{error}"))?;
    }
    let signed_token = match frame_type(&declare_frame)? {
        MESSAGE_TYPE_DECLARE_MINING_JOB_SUCCESS => {
            let reply: DeclareMiningJobSuccess = binary_sv2::from_bytes(declare_frame.payload())
                .map_err(|e| format!("declaration:malformed-success:{e:?}"))?;
            if reply.request_id != 2 {
                return Err("declaration:request-mismatch".to_string());
            }
            reply.new_mining_job_token.to_vec()
        }
        MESSAGE_TYPE_DECLARE_MINING_JOB_ERROR => {
            let reply: DeclareMiningJobError = binary_sv2::from_bytes(declare_frame.payload())
                .map_err(|e| format!("declaration:malformed-error:{e:?}"))?;
            return Err(format!("declaration:{}", reply.error_code.as_utf8_or_hex()));
        }
        kind => return Err(format!("declaration:unexpected-message:{kind}")),
    };

    let (mining_receiver, mining_sender) = encrypted_client(endpoint, public_key, wait).await?;
    negotiate(
        &mining_receiver,
        &mining_sender,
        endpoint,
        Protocol::MiningProtocol,
        MINING_FLAGS,
        wait,
    )
    .await?;
    send(
        &mining_sender,
        WireMessage::Open(OpenExtendedMiningChannel {
            request_id: 3,
            user_identity: b"soveroot-labnet-miner"
                .to_vec()
                .try_into()
                .map_err(|e| format!("identity:{e:?}"))?,
            nominal_hash_rate: 1.0,
            max_target: u256_from_hex(&candidate.target_le_hex, "target", false)?,
            min_extranonce_size: 0,
        }),
    )
    .await?;
    let mut open_frame = receive(&mining_receiver, wait).await?;
    if frame_type(&open_frame)? != MESSAGE_TYPE_OPEN_EXTENDED_MINING_CHANNEL_SUCCESS {
        return Err("mining:open-channel-rejected".to_string());
    }
    let open: OpenExtendedMiningChannelSuccess = binary_sv2::from_bytes(open_frame.payload())
        .map_err(|e| format!("mining:malformed-open:{e:?}"))?;
    if open.request_id != 3 {
        return Err("mining:open-request-mismatch".to_string());
    }
    send(
        &mining_sender,
        WireMessage::SetCustom(custom_job_from_candidate(
            candidate,
            signed_token,
            open.channel_id,
        )?),
    )
    .await?;
    let mut custom_frame = receive(&mining_receiver, wait).await?;
    match frame_type(&custom_frame)? {
        MESSAGE_TYPE_SET_CUSTOM_MINING_JOB_SUCCESS => {
            let reply: SetCustomMiningJobSuccess =
                binary_sv2::from_bytes(custom_frame.payload())
                    .map_err(|e| format!("mining:malformed-custom-success:{e:?}"))?;
            if reply.channel_id != open.channel_id || reply.request_id != 4 {
                return Err("mining:custom-request-mismatch".to_string());
            }
            Ok(reply.job_id)
        }
        MESSAGE_TYPE_SET_CUSTOM_MINING_JOB_ERROR => Err("mining:custom-job-rejected".to_string()),
        kind => Err(format!("mining:unexpected-message:{kind}")),
    }
}

async fn encrypted_server(
    stream: TcpStream,
    public: Secp256k1PublicKey,
    private: Secp256k1SecretKey,
) -> Result<(FrameReceiver, FrameSender)> {
    let responder = Responder::from_authority_kp(
        &public.into_bytes(),
        &private.into_bytes(),
        Duration::from_secs(3600),
    )
    .map_err(|e| format!("responder:{e:?}"))?;
    Connection::new(stream, HandshakeRole::Responder(responder))
        .await
        .map_err(|e| format!("noise:{e:?}"))
}

async fn handle_server_connection(
    stream: TcpStream,
    public: Secp256k1PublicKey,
    private: Secp256k1SecretKey,
    mode: ServerMode,
    state: Arc<Mutex<ServerState>>,
) -> Result<()> {
    let (receiver, sender) = encrypted_server(stream, public, private).await?;
    let mut setup_frame = receive(&receiver, Duration::from_secs(5)).await?;
    if frame_type(&setup_frame)? != MESSAGE_TYPE_SETUP_CONNECTION {
        return Err("expected setup".to_string());
    }
    let setup: SetupConnection =
        binary_sv2::from_bytes(setup_frame.payload()).map_err(|e| format!("setup decode:{e:?}"))?;
    let required = match setup.protocol {
        Protocol::JobDeclarationProtocol => JD_FLAGS,
        Protocol::MiningProtocol => MINING_FLAGS,
        _ => 0,
    };
    let action = if setup.protocol == Protocol::JobDeclarationProtocol {
        let mut guard = state
            .lock()
            .map_err(|_| "coordinator state poisoned".to_string())?;
        guard.job_declaration_sessions = guard.job_declaration_sessions.saturating_add(1);
        mode.action(guard.job_declaration_sessions)
    } else {
        mode
    };
    if required == 0
        || setup.min_version > VERSION
        || setup.max_version < VERSION
        || setup.flags & required != required
    {
        send(
            &sender,
            WireMessage::SetupError(SetupConnectionError {
                flags: required,
                error_code: b"protocol-version-mismatch".to_vec().try_into().unwrap(),
            }),
        )
        .await?;
        return Ok(());
    }
    if action == ServerMode::Downgrade {
        send(
            &sender,
            WireMessage::SetupSuccess(SetupConnectionSuccess {
                used_version: 1,
                flags: 0,
            }),
        )
        .await?;
        return Ok(());
    }
    send(
        &sender,
        WireMessage::SetupSuccess(SetupConnectionSuccess {
            used_version: VERSION,
            flags: required,
        }),
    )
    .await?;
    match setup.protocol {
        Protocol::JobDeclarationProtocol => handle_jd(&receiver, &sender, action, state).await,
        Protocol::MiningProtocol => handle_mining(&receiver, &sender, mode, state).await,
        _ => Ok(()),
    }
}

async fn handle_jd(
    receiver: &FrameReceiver,
    sender: &FrameSender,
    mode: ServerMode,
    state: Arc<Mutex<ServerState>>,
) -> Result<()> {
    let mut token_frame = receive(receiver, Duration::from_secs(5)).await?;
    if frame_type(&token_frame)? != MESSAGE_TYPE_ALLOCATE_MINING_JOB_TOKEN {
        return Err("expected token request".to_string());
    }
    let request: AllocateMiningJobToken =
        binary_sv2::from_bytes(token_frame.payload()).map_err(|e| format!("token decode:{e:?}"))?;
    let mut session_token = vec![0_u8; 24];
    thread_rng().fill_bytes(&mut session_token);
    send(
        sender,
        WireMessage::AllocateSuccess(AllocateMiningJobTokenSuccess {
            request_id: request.request_id,
            mining_job_token: session_token.clone().try_into().unwrap(),
            coinbase_outputs: Vec::<u8>::new().try_into().unwrap(),
        }),
    )
    .await?;
    let mut declare_frame = receive(receiver, Duration::from_secs(5)).await?;
    if frame_type(&declare_frame)? != MESSAGE_TYPE_DECLARE_MINING_JOB {
        return Err("expected declaration".to_string());
    }
    let declaration: DeclareMiningJob = binary_sv2::from_bytes(declare_frame.payload())
        .map_err(|e| format!("declare decode:{e:?}"))?;
    if declaration.mining_job_token.to_vec() != session_token {
        return Err("invalid token".to_string());
    }
    let declared_txids = declaration.tx_ids_list.to_vec();
    if !declared_txids.is_empty() {
        let positions: Vec<u16> = (0..declared_txids.len())
            .map(|position| {
                u16::try_from(position).map_err(|_| "too many declared transactions".to_string())
            })
            .collect::<Result<_>>()?;
        send(
            sender,
            WireMessage::Missing(ProvideMissingTransactions {
                request_id: declaration.request_id,
                unknown_tx_position_list: Seq064K::new(positions)
                    .map_err(|e| format!("missing positions:{e:?}"))?,
            }),
        )
        .await?;
        let mut provided_frame = receive(receiver, Duration::from_secs(5)).await?;
        if frame_type(&provided_frame)? != MESSAGE_TYPE_PROVIDE_MISSING_TRANSACTIONS_SUCCESS {
            return Err("expected missing transactions response".to_string());
        }
        let provided: ProvideMissingTransactionsSuccess =
            binary_sv2::from_bytes(provided_frame.payload())
                .map_err(|e| format!("missing transaction decode:{e:?}"))?;
        if provided.request_id != declaration.request_id {
            return Err("missing transaction request mismatch".to_string());
        }
        let transactions = provided.transaction_list.to_vec();
        if transactions.len() != declared_txids.len() {
            return Err("missing transaction count mismatch".to_string());
        }
        for (transaction, declared_txid) in transactions.iter().zip(declared_txids.iter()) {
            if double_sha256(&transaction.to_vec()) != declared_txid.to_vec() {
                return Err("provided transaction does not match declared txid".to_string());
            }
        }
    }
    if mode == ServerMode::Drop {
        return Ok(());
    }
    if mode == ServerMode::Stall {
        sleep(Duration::from_secs(3)).await;
        return Ok(());
    }
    if mode == ServerMode::Reject {
        send(
            sender,
            WireMessage::DeclareError(DeclareMiningJobError {
                request_id: declaration.request_id,
                error_code: b"policy-rejection".to_vec().try_into().unwrap(),
                error_details: b"test-only rejection".to_vec().try_into().unwrap(),
            }),
        )
        .await?;
        return Ok(());
    }
    if mode == ServerMode::Malformed {
        send(
            sender,
            WireMessage::DeclareSuccess(DeclareMiningJobSuccess {
                request_id: declaration.request_id.saturating_add(1),
                new_mining_job_token: vec![1_u8; 32].try_into().unwrap(),
            }),
        )
        .await?;
        return Ok(());
    }
    let mut signed_token = vec![0_u8; 32];
    thread_rng().fill_bytes(&mut signed_token);
    state
        .lock()
        .map_err(|_| "coordinator state poisoned".to_string())?
        .declared_job = Some(DeclaredJob {
        version: declaration.version,
        token: signed_token.clone(),
        used: false,
    });
    send(
        sender,
        WireMessage::DeclareSuccess(DeclareMiningJobSuccess {
            request_id: declaration.request_id,
            new_mining_job_token: signed_token.try_into().unwrap(),
        }),
    )
    .await
}

async fn handle_mining(
    receiver: &FrameReceiver,
    sender: &FrameSender,
    mode: ServerMode,
    state: Arc<Mutex<ServerState>>,
) -> Result<()> {
    let mut open_frame = receive(receiver, Duration::from_secs(5)).await?;
    if frame_type(&open_frame)? != MESSAGE_TYPE_OPEN_EXTENDED_MINING_CHANNEL {
        return Err("expected open channel".to_string());
    }
    let open: OpenExtendedMiningChannel =
        binary_sv2::from_bytes(open_frame.payload()).map_err(|e| format!("open decode:{e:?}"))?;
    send(
        sender,
        WireMessage::OpenSuccess(OpenExtendedMiningChannelSuccess {
            request_id: open.request_id,
            channel_id: 7,
            target: U256::Owned(open.max_target.to_vec()),
            extranonce_size: 0,
            extranonce_prefix: Vec::<u8>::new().try_into().unwrap(),
        }),
    )
    .await?;
    let mut custom_frame = receive(receiver, Duration::from_secs(5)).await?;
    if frame_type(&custom_frame)? != MESSAGE_TYPE_SET_CUSTOM_MINING_JOB {
        return Err("expected custom job".to_string());
    }
    let custom: SetCustomMiningJob = binary_sv2::from_bytes(custom_frame.payload())
        .map_err(|e| format!("custom decode:{e:?}"))?;
    let accepted = {
        let mut guard = state
            .lock()
            .map_err(|_| "coordinator state poisoned".to_string())?;
        guard
            .declared_job
            .as_mut()
            .map(|job| job.consume_custom_job(custom.version, &custom.token.to_vec()))
            .unwrap_or(false)
    };
    if accepted {
        let job_id = {
            let mut guard = state
                .lock()
                .map_err(|_| "coordinator state poisoned".to_string())?;
            guard.accepted_custom_jobs = guard.accepted_custom_jobs.saturating_add(1);
            if mode == ServerMode::Equivocate {
                8 + guard.accepted_custom_jobs
            } else {
                9
            }
        };
        send(
            sender,
            WireMessage::SetCustomSuccess(SetCustomMiningJobSuccess {
                channel_id: custom.channel_id,
                request_id: custom.request_id,
                job_id,
            }),
        )
        .await
    } else {
        send(
            sender,
            WireMessage::SetCustomError(SetCustomMiningJobError {
                channel_id: custom.channel_id,
                request_id: custom.request_id,
                error_code: b"invalid-mining-job-token".to_vec().try_into().unwrap(),
            }),
        )
        .await
    }
}

fn generate_authority(path: &Path) -> Result<()> {
    let secp = Secp256k1::new();
    let (secret, public) = loop {
        let (secret, _) = secp.generate_keypair(&mut thread_rng());
        let keypair = Keypair::from_secret_key(&secp, &secret);
        let (public, parity) = keypair.x_only_public_key();
        if parity == Parity::Even {
            break (Secp256k1SecretKey(secret), Secp256k1PublicKey(public));
        }
    };
    let body = serde_json::to_vec(&AuthorityFile {
        public_key: public.to_string(),
        private_key: secret.to_string(),
    })
    .map_err(|e| e.to_string())?;
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(path)
        .map_err(|e| format!("cannot create authority file: {e}"))?;
    file.write_all(&body)
        .map_err(|e| format!("cannot write authority file: {e}"))?;
    println!("{}", public);
    Ok(())
}

fn load_authority(path: &Path) -> Result<(Secp256k1PublicKey, Secp256k1SecretKey)> {
    let value: AuthorityFile = serde_json::from_slice(
        &fs::read(path).map_err(|e| format!("cannot read authority file: {e}"))?,
    )
    .map_err(|e| format!("authority JSON: {e}"))?;
    let public = value
        .public_key
        .parse()
        .map_err(|e| format!("public key: {e}"))?;
    let private = value
        .private_key
        .parse()
        .map_err(|e| format!("private key: {e}"))?;
    Ok((public, private))
}

fn args_map(values: &[String]) -> Result<HashMap<String, String>> {
    if !values.len().is_multiple_of(2) {
        return Err("options must be --name value pairs".to_string());
    }
    let mut result = HashMap::new();
    for pair in values.chunks(2) {
        if !pair[0].starts_with("--") {
            return Err(format!("invalid option {}", pair[0]));
        }
        result.insert(pair[0].clone(), pair[1].clone());
    }
    Ok(result)
}

fn required(map: &HashMap<String, String>, name: &str) -> Result<String> {
    map.get(name)
        .cloned()
        .ok_or_else(|| format!("missing {name}"))
}

#[tokio::main]
async fn main() {
    if let Err(error) = real_main().await {
        eprintln!("Error: {error}");
        std::process::exit(2);
    }
}

async fn real_main() -> Result<()> {
    let args: Vec<String> = env::args().skip(1).collect();
    let command = args.first().ok_or_else(|| {
        "expected generate-authority, serve, declare, or vector-report".to_string()
    })?;
    let options = args_map(&args[1..])?;
    match command.as_str() {
        "vector-report" => {
            let path = PathBuf::from(required(&options, "--fixture")?);
            let fixture: InteropFixture = serde_json::from_slice(
                &fs::read(&path)
                    .map_err(|error| format!("cannot read fixture {}: {error}", path.display()))?,
            )
            .map_err(|error| format!("fixture JSON: {error}"))?;
            let report = interop_wire_report(fixture)?;
            println!(
                "{}",
                serde_json::to_string(&report).map_err(|error| error.to_string())?
            );
            Ok(())
        }
        "generate-authority" => generate_authority(&PathBuf::from(required(&options, "--output")?)),
        "serve" => {
            let endpoint = required(&options, "--endpoint")?;
            let (public, private) =
                load_authority(&PathBuf::from(required(&options, "--authority-file")?))?;
            let mode = match options
                .get("--mode")
                .map(String::as_str)
                .unwrap_or("accept")
            {
                "accept" => ServerMode::Accept,
                "reject" => ServerMode::Reject,
                "drop" => ServerMode::Drop,
                "stall" => ServerMode::Stall,
                "malformed" => ServerMode::Malformed,
                "downgrade" => ServerMode::Downgrade,
                "scenario" => ServerMode::Scenario,
                "equivocate" => ServerMode::Equivocate,
                other => return Err(format!("unknown server mode {other}")),
            };
            let listener = TcpListener::bind(&endpoint)
                .await
                .map_err(|e| format!("bind {endpoint}: {e}"))?;
            if let Some(path) = options.get("--ready-file") {
                fs::write(
                    path,
                    serde_json::to_vec(&AuthorityFile {
                        public_key: public.to_string(),
                        private_key: "redacted".to_string(),
                    })
                    .unwrap(),
                )
                .map_err(|e| format!("ready file: {e}"))?;
            }
            let state = Arc::new(Mutex::new(ServerState::default()));
            loop {
                let (stream, _) = listener
                    .accept()
                    .await
                    .map_err(|e| format!("accept: {e}"))?;
                let state = state.clone();
                tokio::spawn(async move {
                    if let Err(error) =
                        handle_server_connection(stream, public, private, mode, state).await
                    {
                        eprintln!("coordinator connection: {error}");
                    }
                });
            }
        }
        "declare" => {
            let endpoint = required(&options, "--endpoint")?;
            let key = required(&options, "--authority-public-key")?;
            let wait = Duration::from_millis(
                required(&options, "--timeout-ms")?
                    .parse()
                    .map_err(|_| "timeout must be an integer".to_string())?,
            );
            let mut input = String::new();
            io::stdin()
                .read_to_string(&mut input)
                .map_err(|e| e.to_string())?;
            let candidate: Candidate =
                serde_json::from_str(&input).map_err(|e| format!("candidate JSON: {e}"))?;
            let result = match run_client(&endpoint, &key, wait, &candidate).await {
                Ok(job_id) => ClientResult {
                    status: "accepted",
                    transport_status: "authenticated",
                    template_commitment_sha256: &candidate.template_commitment_sha256,
                    reason: None,
                    job_id: Some(job_id),
                    coordinator_state_commitment: Some(encode_hex(&Sha256::digest(
                        format!(
                            "soveroot-coordinator-view-v0:{}:{job_id}",
                            candidate.template_commitment_sha256
                        )
                        .as_bytes(),
                    ))),
                },
                Err(reason) => {
                    let transport_status = if reason.starts_with("transport:") {
                        "failed"
                    } else {
                        "authenticated"
                    };
                    ClientResult {
                        status: "direct_fallback",
                        transport_status,
                        template_commitment_sha256: &candidate.template_commitment_sha256,
                        reason: Some(reason),
                        job_id: None,
                        coordinator_state_commitment: None,
                    }
                }
            };
            println!(
                "{}",
                serde_json::to_string(&result).map_err(|e| e.to_string())?
            );
            Ok(())
        }
        other => Err(format!("unknown command {other}")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn candidate() -> Candidate {
        Candidate {
            chain: "labnet".to_string(),
            previous_block_hash: "00".repeat(32),
            version: 4,
            bits: 0x207f_ffff,
            curtime: 1,
            coinbase_tx_version: 2,
            coinbase_prefix_hex: format!("0200000001{}ffffffff01", "00".repeat(32)),
            coinbase_suffix_hex: "ffffffff0100f2052a01000000015100000000".to_string(),
            coinbase_outputs_hex: "0100f2052a010000000151".to_string(),
            coinbase_tx_input_n_sequence: u32::MAX,
            coinbase_tx_locktime: 0,
            transaction_ids: vec!["01".repeat(32)],
            transaction_data: vec!["0102".to_string()],
            coinbase_merkle_path: vec!["02".repeat(32)],
            target_le_hex: format!("{}7f", "ff".repeat(31)),
            template_commitment_sha256: "11".repeat(32),
        }
    }

    #[test]
    fn declared_job_binary_round_trip_preserves_miner_fields() {
        let expected = declaration_from_candidate(&candidate(), b"test-token".to_vec()).unwrap();
        let mut payload = binary_sv2::to_bytes(expected.clone()).unwrap();
        let decoded: DeclareMiningJob = binary_sv2::from_bytes(&mut payload).unwrap();
        assert_eq!(decoded, expected);
    }

    #[test]
    fn custom_job_binary_round_trip_preserves_miner_fields() {
        let expected =
            custom_job_from_candidate(&candidate(), b"test-signed-token".to_vec(), 7).unwrap();
        let mut payload = binary_sv2::to_bytes(expected.clone()).unwrap();
        let decoded: SetCustomMiningJob = binary_sv2::from_bytes(&mut payload).unwrap();
        assert_eq!(decoded, expected);
    }

    #[test]
    fn custom_job_token_is_single_use() {
        let mut declared = DeclaredJob {
            version: 4,
            token: b"one-time-token".to_vec(),
            used: false,
        };
        assert!(declared.consume_custom_job(4, b"one-time-token"));
        assert!(!declared.consume_custom_job(4, b"one-time-token"));
    }
}
