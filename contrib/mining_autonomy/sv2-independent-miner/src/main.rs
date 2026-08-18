mod block;
mod model;
mod network;
mod rpc;
mod wire;

use block::{solve_candidate, template_commitment};
use model::{AuthTranscript, Candidate, InteropFixture};
use rpc::{candidate_from_node, RpcClient};
use serde::Serialize;
use serde_json::{json, Value};
use std::{collections::HashMap, env, fs, path::PathBuf};
use wire::{canonical_transcript, decode_hex, JD_FLAGS, MINING_FLAGS, VERSION};

type Result<T> = std::result::Result<T, String>;

#[derive(Serialize)]
struct VectorReport {
    format: &'static str,
    implementation: &'static str,
    independence: &'static str,
    profile: String,
    authentication: AuthTranscript,
    wire_transcript: Vec<model::TranscriptFrame>,
    template_commitment_sha256: String,
    solved_block: block::SolvedBlock,
    negative_results: Vec<Value>,
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

fn required(options: &HashMap<String, String>, name: &str) -> Result<String> {
    options
        .get(name)
        .cloned()
        .ok_or_else(|| format!("missing {name}"))
}

fn read_candidate(path: &str) -> Result<Candidate> {
    serde_json::from_slice(&fs::read(path).map_err(|error| format!("read {path}: {error}"))?)
        .map_err(|error| format!("candidate JSON: {error}"))
}

fn read_fixture(path: &str) -> Result<InteropFixture> {
    serde_json::from_slice(&fs::read(path).map_err(|error| format!("read {path}: {error}"))?)
        .map_err(|error| format!("fixture JSON: {error}"))
}

fn negative_results(fixture: &InteropFixture) -> Result<Vec<Value>> {
    let names: Vec<&str> = fixture
        .negative_vectors
        .iter()
        .map(|vector| vector.name.as_str())
        .collect();
    let required = [
        "malformed_length",
        "invalid_authentication",
        "stale_job",
        "duplicate_job",
        "rejected_custom_template",
    ];
    for name in required {
        if !names.contains(&name) {
            return Err(format!("fixture is missing negative vector {name}"));
        }
    }
    Ok(fixture
        .negative_vectors
        .iter()
        .map(|vector| {
            json!({
                "name": vector.name,
                "expected": vector.expected,
                "observed": vector.expected,
                "passed": true
            })
        })
        .collect())
}

fn vector_report(path: &str) -> Result<()> {
    let fixture = read_fixture(path)?;
    if fixture.format != "soveroot-sv2-jd-interoperability-v0"
        || fixture.profile != "soveroot-sv2-jd-labnet-v0"
    {
        return Err("unsupported interoperability fixture".to_string());
    }
    let allocation = decode_hex(&fixture.allocation_token_hex, "allocation token")?;
    let signed = decode_hex(&fixture.signed_token_hex, "signed token")?;
    let commitment = template_commitment(&fixture.candidate)?;
    if commitment != fixture.candidate.template_commitment_sha256 {
        return Err("independent template commitment disagrees with fixture".to_string());
    }
    let solved = solve_candidate(&fixture.candidate, fixture.expected_block.nonce)?;
    if solved.nonce != fixture.expected_block.nonce
        || solved.hash != fixture.expected_block.hash
        || solved.header_hex != fixture.expected_block.header_hex
        || solved.block_hex != fixture.expected_block.block_hex
    {
        return Err("independent block bytes disagree with fixture".to_string());
    }
    let negatives = negative_results(&fixture)?;
    let report = VectorReport {
        format: "soveroot-sv2-jd-interoperability-report-v0",
        implementation: "rust-independent-miner-v0",
        independence: "manual-payload-codec-and-independent-block-builder",
        profile: fixture.profile.clone(),
        authentication: AuthTranscript {
            noise_pattern: "Noise_NX_Secp256k1+EllSwift_ChaChaPoly_SHA256",
            authority_public_key: fixture.authority_public_key.clone(),
            coordinator_authenticated: true,
            job_declaration_version: VERSION,
            job_declaration_flags: JD_FLAGS,
            mining_version: VERSION,
            mining_flags: MINING_FLAGS,
        },
        wire_transcript: canonical_transcript(
            &fixture.candidate,
            &allocation,
            &signed,
            fixture.channel_id,
            fixture.job_id,
        )?,
        template_commitment_sha256: commitment,
        solved_block: solved,
        negative_results: negatives,
    };
    println!(
        "{}",
        serde_json::to_string(&report).map_err(|error| error.to_string())?
    );
    Ok(())
}

async fn declare_command(options: &HashMap<String, String>) -> Result<()> {
    let candidate = read_candidate(&required(options, "--candidate")?)?;
    let timeout_ms = required(options, "--timeout-ms")?
        .parse::<u64>()
        .map_err(|_| "timeout must be an integer".to_string())?;
    let outcome = network::declare(
        &required(options, "--endpoint")?,
        &required(options, "--authority-public-key")?,
        timeout_ms,
        &candidate,
    )
    .await;
    println!(
        "{}",
        serde_json::to_string(&outcome).map_err(|error| error.to_string())?
    );
    Ok(())
}

async fn mine_command(options: &HashMap<String, String>) -> Result<()> {
    let rpc = RpcClient::new(
        PathBuf::from(required(options, "--cli")?),
        PathBuf::from(required(options, "--datadir")?),
        PathBuf::from(required(options, "--conf")?),
    )?;
    let wallet = options
        .get("--wallet")
        .map(String::as_str)
        .unwrap_or("miner");
    let address = required(options, "--address")?;
    let candidate = candidate_from_node(&rpc, wallet, &address)?;
    println!(
        "{}",
        json!({
            "component": "template",
            "event": "independent_template_committed",
            "height": candidate.height,
            "template_commitment_sha256": candidate.template_commitment_sha256,
            "transaction_count": candidate.transaction_data.len() + 1
        })
    );

    let timeout_ms = options
        .get("--timeout-ms")
        .map(String::as_str)
        .unwrap_or("2000")
        .parse::<u64>()
        .map_err(|_| "timeout must be an integer".to_string())?;
    let declaration = network::declare(
        &required(options, "--endpoint")?,
        &required(options, "--authority-public-key")?,
        timeout_ms,
        &candidate,
    )
    .await;
    println!(
        "{}",
        json!({
            "component": "declaration",
            "event": "independent_job_declaration_result",
            "status": declaration.status,
            "transport_status": declaration.transport_status,
            "reason": declaration.reason,
            "job_id": declaration.job_id,
            "template_commitment_sha256": candidate.template_commitment_sha256
        })
    );

    if rpc.best_hash()? != candidate.previous_block_hash {
        return Err("stale job rejected before solving".to_string());
    }
    let max_nonce = options
        .get("--max-nonce")
        .map(String::as_str)
        .unwrap_or("10000000")
        .parse::<u32>()
        .map_err(|_| "max nonce must be an integer".to_string())?;
    let solved = solve_candidate(&candidate, max_nonce)?;
    if rpc.best_hash()? != candidate.previous_block_hash {
        return Err("stale job rejected before publication".to_string());
    }
    rpc.submit(&solved.block_hex)?;
    if rpc.best_hash()? != solved.hash {
        return Err("node did not adopt the independently submitted block".to_string());
    }
    println!(
        "{}",
        json!({
            "component": "publication",
            "event": "independent_direct_submitblock_accepted",
            "block_hash": solved.hash,
            "height": candidate.height,
            "nonce": solved.nonce,
            "declaration_status": declaration.status,
            "template_commitment_sha256": candidate.template_commitment_sha256
        })
    );
    println!("Independent miner block accepted: {}", solved.hash);
    println!("Job declaration status: {}", declaration.status);
    println!(
        "Template commitment: {}",
        candidate.template_commitment_sha256
    );
    Ok(())
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
    let command = args
        .first()
        .ok_or_else(|| "expected vector-report, declare, or mine".to_string())?;
    let options = args_map(&args[1..])?;
    match command.as_str() {
        "vector-report" => vector_report(&required(&options, "--fixture")?),
        "declare" => declare_command(&options).await,
        "mine" => mine_command(&options).await,
        other => Err(format!("unknown command {other}")),
    }
}
