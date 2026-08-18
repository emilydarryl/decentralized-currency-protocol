use crate::{
    model::{Candidate, TranscriptFrame},
    wire::{
        allocate_payload, declare_payload, missing_success_payload, open_channel_payload,
        parse_allocate_success, parse_declare_error, parse_declare_success, parse_missing,
        parse_open_success, parse_set_custom_error, parse_set_custom_success, parse_setup_success,
        record, set_custom_payload, setup_payload, RawPayload, Result, JD_FLAGS, MINING_FLAGS,
        MSG_ALLOCATE_TOKEN, MSG_ALLOCATE_TOKEN_SUCCESS, MSG_DECLARE, MSG_DECLARE_ERROR,
        MSG_DECLARE_SUCCESS, MSG_OPEN_ERROR, MSG_OPEN_EXTENDED, MSG_OPEN_EXTENDED_SUCCESS,
        MSG_PROVIDE_MISSING, MSG_PROVIDE_MISSING_SUCCESS, MSG_SETUP, MSG_SETUP_ERROR,
        MSG_SETUP_SUCCESS, MSG_SET_CUSTOM, MSG_SET_CUSTOM_ERROR, MSG_SET_CUSTOM_SUCCESS,
    },
};
use async_channel::{Receiver, Sender};
use codec_sv2::{HandshakeRole, Initiator, StandardEitherFrame, StandardSv2Frame};
use key_utils::Secp256k1PublicKey;
use network_helpers_sv2::noise_connection::Connection;
use serde::Serialize;
use std::{collections::HashSet, convert::TryInto, time::Duration};
use tokio::{net::TcpStream, time::timeout};

type EitherFrame = StandardEitherFrame<RawPayload>;
type FrameReceiver = Receiver<EitherFrame>;
type FrameSender = Sender<EitherFrame>;

#[derive(Clone, Debug, Serialize)]
pub struct DeclarationOutcome {
    pub status: &'static str,
    pub transport_status: &'static str,
    pub template_commitment_sha256: String,
    pub reason: Option<String>,
    pub job_id: Option<u32>,
    pub transcript: Vec<TranscriptFrame>,
}

async fn connect(
    endpoint: &str,
    authority_public_key: &str,
    wait: Duration,
) -> Result<(FrameReceiver, FrameSender)> {
    let stream = timeout(wait, TcpStream::connect(endpoint))
        .await
        .map_err(|_| "transport:connect-timeout".to_string())?
        .map_err(|error| format!("transport:connect:{error}"))?;
    let public: Secp256k1PublicKey = authority_public_key
        .parse()
        .map_err(|error| format!("transport:authority-key:{error}"))?;
    let initiator = Initiator::from_raw_k(public.into_bytes())
        .map_err(|error| format!("transport:initiator:{error:?}"))?;
    timeout(
        wait,
        Connection::new(stream, HandshakeRole::Initiator(initiator)),
    )
    .await
    .map_err(|_| "transport:noise-timeout".to_string())?
    .map_err(|error| format!("transport:noise-authentication:{error:?}"))
}

async fn send(
    sender: &FrameSender,
    message_type: u8,
    payload: Vec<u8>,
    transcript: &mut Vec<TranscriptFrame>,
) -> Result<()> {
    transcript.push(record("miner_to_coordinator", message_type, &payload));
    let frame = StandardSv2Frame::from_message(RawPayload(payload), message_type, 0, false)
        .ok_or_else(|| "transport:cannot-encode-frame".to_string())?;
    sender
        .send(frame.into())
        .await
        .map_err(|_| "transport:connection-closed-while-sending".to_string())
}

async fn receive(
    receiver: &FrameReceiver,
    wait: Duration,
    transcript: &mut Vec<TranscriptFrame>,
) -> Result<(u8, Vec<u8>)> {
    let frame = timeout(wait, receiver.recv())
        .await
        .map_err(|_| "transport:timeout".to_string())?
        .map_err(|_| "transport:connection-closed".to_string())?;
    let mut frame: StandardSv2Frame<RawPayload> = frame
        .try_into()
        .map_err(|error| format!("transport:malformed-frame:{error:?}"))?;
    let header = frame
        .get_header()
        .ok_or_else(|| "transport:missing-header".to_string())?;
    if header.ext_type() != 0 {
        return Err(format!(
            "transport:unsupported-extension:{}",
            header.ext_type()
        ));
    }
    let message_type = header.msg_type();
    let payload = frame.payload().to_vec();
    transcript.push(record("coordinator_to_miner", message_type, &payload));
    Ok((message_type, payload))
}

fn endpoint_port(endpoint: &str) -> Result<u16> {
    endpoint
        .rsplit_once(':')
        .ok_or_else(|| "endpoint must be host:port".to_string())?
        .1
        .parse()
        .map_err(|_| "endpoint port is invalid".to_string())
}

async fn negotiate(
    receiver: &FrameReceiver,
    sender: &FrameSender,
    endpoint: &str,
    protocol: u8,
    flags: u32,
    wait: Duration,
    transcript: &mut Vec<TranscriptFrame>,
) -> Result<()> {
    send(
        sender,
        MSG_SETUP,
        setup_payload(protocol, flags, endpoint_port(endpoint)?)?,
        transcript,
    )
    .await?;
    let (kind, payload) = receive(receiver, wait, transcript).await?;
    match kind {
        MSG_SETUP_SUCCESS => parse_setup_success(&payload, flags),
        MSG_SETUP_ERROR => Err("setup:rejected".to_string()),
        other => Err(format!("setup:unexpected-message:{other}")),
    }
}

async fn declare_inner(
    endpoint: &str,
    authority_public_key: &str,
    wait: Duration,
    candidate: &Candidate,
) -> Result<(u32, Vec<TranscriptFrame>)> {
    if candidate.chain != "labnet" {
        return Err("declaration:chain-not-labnet".to_string());
    }
    let mut transcript = Vec::new();
    let (jd_receiver, jd_sender) = connect(endpoint, authority_public_key, wait).await?;
    negotiate(
        &jd_receiver,
        &jd_sender,
        endpoint,
        1,
        JD_FLAGS,
        wait,
        &mut transcript,
    )
    .await?;

    send(
        &jd_sender,
        MSG_ALLOCATE_TOKEN,
        allocate_payload(1)?,
        &mut transcript,
    )
    .await?;
    let (kind, payload) = receive(&jd_receiver, wait, &mut transcript).await?;
    if kind != MSG_ALLOCATE_TOKEN_SUCCESS {
        return Err(format!("declaration:unexpected-token-message:{kind}"));
    }
    let allocation_token = parse_allocate_success(&payload, 1)?;

    send(
        &jd_sender,
        MSG_DECLARE,
        declare_payload(candidate, &allocation_token, 2)?,
        &mut transcript,
    )
    .await?;
    let signed_token = loop {
        let (kind, payload) = receive(&jd_receiver, wait, &mut transcript).await?;
        match kind {
            MSG_PROVIDE_MISSING => {
                let positions = parse_missing(&payload, 2)?;
                let unique: HashSet<u16> = positions.iter().copied().collect();
                if unique.len() != positions.len() {
                    return Err("declaration:duplicate-missing-position".to_string());
                }
                send(
                    &jd_sender,
                    MSG_PROVIDE_MISSING_SUCCESS,
                    missing_success_payload(candidate, 2, &positions)?,
                    &mut transcript,
                )
                .await?;
            }
            MSG_DECLARE_SUCCESS => break parse_declare_success(&payload, 2)?,
            MSG_DECLARE_ERROR => {
                let code = parse_declare_error(&payload, 2)?;
                return Err(format!("declaration:{code}"));
            }
            other => return Err(format!("declaration:unexpected-message:{other}")),
        }
    };
    drop(jd_sender);
    drop(jd_receiver);

    let (mining_receiver, mining_sender) = connect(endpoint, authority_public_key, wait).await?;
    negotiate(
        &mining_receiver,
        &mining_sender,
        endpoint,
        0,
        MINING_FLAGS,
        wait,
        &mut transcript,
    )
    .await?;
    send(
        &mining_sender,
        MSG_OPEN_EXTENDED,
        open_channel_payload(candidate, 3)?,
        &mut transcript,
    )
    .await?;
    let (kind, payload) = receive(&mining_receiver, wait, &mut transcript).await?;
    let channel_id = match kind {
        MSG_OPEN_EXTENDED_SUCCESS => parse_open_success(&payload, 3)?,
        MSG_OPEN_ERROR => return Err("mining:open-channel-rejected".to_string()),
        other => return Err(format!("mining:unexpected-open-message:{other}")),
    };

    send(
        &mining_sender,
        MSG_SET_CUSTOM,
        set_custom_payload(candidate, &signed_token, channel_id, 4)?,
        &mut transcript,
    )
    .await?;
    let (kind, payload) = receive(&mining_receiver, wait, &mut transcript).await?;
    let job_id = match kind {
        MSG_SET_CUSTOM_SUCCESS => parse_set_custom_success(&payload, channel_id, 4)?,
        MSG_SET_CUSTOM_ERROR => {
            let code = parse_set_custom_error(&payload, channel_id, 4)?;
            return Err(format!("mining:{code}"));
        }
        other => return Err(format!("mining:unexpected-custom-message:{other}")),
    };
    Ok((job_id, transcript))
}

pub async fn declare(
    endpoint: &str,
    authority_public_key: &str,
    timeout_ms: u64,
    candidate: &Candidate,
) -> DeclarationOutcome {
    let wait = Duration::from_millis(timeout_ms);
    match declare_inner(endpoint, authority_public_key, wait, candidate).await {
        Ok((job_id, transcript)) => DeclarationOutcome {
            status: "accepted",
            transport_status: "authenticated",
            template_commitment_sha256: candidate.template_commitment_sha256.clone(),
            reason: None,
            job_id: Some(job_id),
            transcript,
        },
        Err(reason) => DeclarationOutcome {
            status: "direct_fallback",
            transport_status: if reason.starts_with("transport:") {
                "failed"
            } else {
                "authenticated"
            },
            template_commitment_sha256: candidate.template_commitment_sha256.clone(),
            reason: Some(reason),
            job_id: None,
            transcript: Vec::new(),
        },
    }
}
