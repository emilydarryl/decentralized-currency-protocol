use crate::{
    block::{
        build_coinbase, coinbase_merkle_path, hash256, merkle_root, target_from_compact,
        template_commitment,
    },
    model::Candidate,
    wire::{decode_hex, encode_hex, Result},
};
use serde_json::{json, Value};
use std::{path::PathBuf, process::Command};

#[derive(Clone, Debug)]
pub struct RpcClient {
    cli: PathBuf,
    datadir: PathBuf,
    config: PathBuf,
}

impl RpcClient {
    pub fn new(cli: PathBuf, datadir: PathBuf, config: PathBuf) -> Result<Self> {
        if !cli.is_file() {
            return Err(format!("sovr-cli was not found at {}", cli.display()));
        }
        Ok(Self {
            cli,
            datadir,
            config,
        })
    }

    pub fn call(&self, method: &str, arguments: &[String], wallet: Option<&str>) -> Result<Value> {
        let mut command = Command::new(&self.cli);
        command
            .arg("-chain=labnet")
            .arg(format!("-datadir={}", self.datadir.display()))
            .arg(format!("-conf={}", self.config.display()));
        if let Some(wallet) = wallet {
            command.arg(format!("-rpcwallet={wallet}"));
        }
        command.arg(method).args(arguments);
        let output = command
            .output()
            .map_err(|error| format!("cannot run sovr-cli for {method}: {error}"))?;
        if !output.status.success() {
            return Err(format!(
                "sovr-cli call failed for {method}: {}",
                String::from_utf8_lossy(&output.stderr).trim()
            ));
        }
        let text = String::from_utf8(output.stdout)
            .map_err(|_| format!("sovr-cli returned non-UTF8 output for {method}"))?;
        let text = text.trim();
        if text.is_empty() {
            return Ok(Value::Null);
        }
        serde_json::from_str(text).or_else(|_| Ok(Value::String(text.to_string())))
    }

    pub fn best_hash(&self) -> Result<String> {
        self.call("getbestblockhash", &[], None)?
            .as_str()
            .map(str::to_string)
            .ok_or_else(|| "getbestblockhash returned a non-string".to_string())
    }

    pub fn submit(&self, block_hex: &str) -> Result<()> {
        let response = self.call("submitblock", &[block_hex.to_string()], None)?;
        if !response.is_null() && response.as_str() != Some("null") {
            return Err(format!(
                "node rejected independently built block: {response}"
            ));
        }
        Ok(())
    }
}

fn object<'a>(value: &'a Value, label: &str) -> Result<&'a serde_json::Map<String, Value>> {
    value
        .as_object()
        .ok_or_else(|| format!("{label} RPC response is not an object"))
}

fn string_field<'a>(value: &'a serde_json::Map<String, Value>, name: &str) -> Result<&'a str> {
    value
        .get(name)
        .and_then(Value::as_str)
        .ok_or_else(|| format!("missing or invalid string field {name}"))
}

fn u64_field(value: &serde_json::Map<String, Value>, name: &str) -> Result<u64> {
    value
        .get(name)
        .and_then(Value::as_u64)
        .ok_or_else(|| format!("missing or invalid integer field {name}"))
}

pub fn candidate_from_node(rpc: &RpcClient, wallet: &str, address: &str) -> Result<Candidate> {
    let chain_value = rpc.call("getblockchaininfo", &[], None)?;
    let chain = object(&chain_value, "getblockchaininfo")?;
    if string_field(chain, "chain")? != "labnet" {
        return Err("refusing to mine: connected node is not chain=labnet".to_string());
    }
    let best_hash = string_field(chain, "bestblockhash")?.to_string();

    let address_value = rpc.call("getaddressinfo", &[address.to_string()], Some(wallet))?;
    let address_info = object(&address_value, "getaddressinfo")?;
    let payout_script = decode_hex(string_field(address_info, "scriptPubKey")?, "payout script")?;

    let request =
        serde_json::to_string(&json!({"rules": ["segwit"]})).map_err(|error| error.to_string())?;
    let template_value = rpc.call("getblocktemplate", &[request], None)?;
    let template = object(&template_value, "getblocktemplate")?;
    let previous_block_hash = string_field(template, "previousblockhash")?.to_string();
    if previous_block_hash != best_hash {
        return Err("block template was stale before construction".to_string());
    }

    let version = u32::try_from(u64_field(template, "version")?)
        .map_err(|_| "template version exceeds uint32".to_string())?;
    let height = u64_field(template, "height")?;
    let coinbase_value = u64_field(template, "coinbasevalue")?;
    let curtime = u32::try_from(u64_field(template, "curtime")?)
        .map_err(|_| "template curtime exceeds uint32".to_string())?;
    let bits = u32::from_str_radix(string_field(template, "bits")?, 16)
        .map_err(|_| "template bits are not hexadecimal".to_string())?;

    let flags = template
        .get("coinbaseaux")
        .and_then(Value::as_object)
        .and_then(|value| value.get("flags"))
        .and_then(Value::as_str)
        .unwrap_or("");
    let flags = decode_hex(flags, "coinbase flags")?;
    let witness = template
        .get("default_witness_commitment")
        .and_then(Value::as_str)
        .map(|value| decode_hex(value, "witness commitment"))
        .transpose()?;
    let coinbase = build_coinbase(
        height,
        coinbase_value,
        &payout_script,
        &flags,
        witness.as_deref(),
    )?;

    let transactions = template
        .get("transactions")
        .and_then(Value::as_array)
        .ok_or_else(|| "template transactions is not an array".to_string())?;
    let mut hashes = vec![coinbase.txid_hash];
    let mut transaction_ids = Vec::with_capacity(transactions.len());
    let mut transaction_data = Vec::with_capacity(transactions.len());
    for (index, transaction) in transactions.iter().enumerate() {
        let transaction = object(transaction, &format!("transaction {index}"))?;
        let txid = string_field(transaction, "txid")?.to_string();
        let data_hex = string_field(transaction, "data")?.to_string();
        let data = decode_hex(&data_hex, "transaction data")?;
        let digest = hash256(&data);
        let mut display = digest;
        display.reverse();
        if encode_hex(&display) != txid {
            return Err(format!("transaction {index} data does not match its txid"));
        }
        hashes.push(digest);
        transaction_ids.push(txid);
        transaction_data.push(data_hex);
    }

    let root = merkle_root(hashes.clone())?;
    let path = coinbase_merkle_path(hashes)?;
    let target = target_from_compact(bits)?;
    let mut candidate = Candidate {
        chain: "labnet".to_string(),
        height,
        previous_block_hash,
        version,
        bits,
        curtime,
        coinbase_value,
        payout_script_hex: encode_hex(&payout_script),
        coinbase_tx_version: 2,
        coinbase_prefix_hex: encode_hex(&coinbase.declaration_prefix),
        coinbase_suffix_hex: encode_hex(&coinbase.declaration_suffix),
        coinbase_tx_hex: encode_hex(&coinbase.block_bytes),
        coinbase_outputs_hex: encode_hex(&coinbase.serialized_outputs),
        coinbase_tx_input_n_sequence: u32::MAX,
        coinbase_tx_locktime: 0,
        transaction_ids,
        transaction_data,
        coinbase_merkle_path: path.iter().map(|hash| encode_hex(hash)).collect(),
        merkle_root_internal_hex: encode_hex(&root),
        target_le_hex: encode_hex(&target),
        template_commitment_sha256: String::new(),
    };
    candidate.template_commitment_sha256 = template_commitment(&candidate)?;
    Ok(candidate)
}

#[cfg(test)]
mod tests {
    #[test]
    fn rpc_command_is_permanently_labnet_scoped() {
        let source = include_str!("rpc.rs");
        assert!(source.contains("-chain=labnet"));
    }
}
