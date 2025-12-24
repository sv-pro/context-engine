# Jira issues (50)

- **CDDOS-1876**: Remove Priority handling for DPX | None | Unassigned | 2025-12-23T16:00:02.168+0300
  In DPX the priority ordering is handled by pre-configuration (need to be enabled on every new DPX deployment)
  For driver 10.X stream we need to remove priority settings in policy text “-p”
  priority will be handled automatically within the DP device.

- **CDDOS-906**: PO Onboarding - CHARTER (non cloud) | None | Unassigned | 2025-12-23T15:19:16.678+0300
  Enable onboarding and configuration of Protected Objects (POs) and their thresholds in the Unified Portal for CHARTER-like customers with Cyber Controller (CC) integration, with:
  - Operator – limited edit permissions
  - Regular User – view-only
  Roles:
  - Operator
    - Manage(Edit) Asset BW → which is translated to thresholds 
  - Account Admin and Asset Admin
    - View-only access to Asset BW 
  
  PO Onboarding Process
  - Enable setting of PO thresholds per asset in the portal.
  - PO naming format == UID_Asset  please check with Michael if need to change for activate/deactivate
    need to update the Threshold view:
  
  Account Configuration: Cyber Controller Workflow Mapping
  
  MSSP Account SETTINGS
  Location: MSSP Account → “MSSP Infrastructure Protection”: ->Cyber Controller Configuration section
  Enable/Disable CC Integration → Will open CC IP settings
  Under this section we need to move the CC integration. All Cyber controllers for child accounts bind list will derive from these settings (today child account level).
  - Previous Location: Account → Infrastructure Settings → Cyber Controller Settings (OPERATOR ONLY) will have only the enable /disable CC integration toggle. 
  Location: MSSP Account → MSSP Infrastructure Protection”: ->Cyber Controller Configuration section
  - Sites
  Each Cyber Controller (CC) integrated account is created with at least two predefined Sites. To support consistent onboarding and reuse, Site settings are managed at the MSSP level and inherited by Accounts. Site will hold predefined sites + connections baselines. Change to baseline will impact new onboardings only → no impact on existing ones.
  - Tabs
    - Sites
    - 
    - Define and manage the MSSP-level Sites (names, settings, defaults). These Sites are inherited by Accounts created under the MSSP.
    - WIthin Sites → Site Connections
    - 
      additional Column for connections that needs to be propagated is “Nickname” (later to map for onboarding purposes)
      Define how Sites connect to CC-integrated Accounts.
  - Add section: “Set Workflows” – free text list.
  - Tooltip:
    “Define the Cyber Controller Workflow names for this account, as used at the asset level. Names must match the exact syntax in Cyber Controller.”
  - Validation:
    - Allowed characters: [a-zA-Z_]
    - Max length: 30 characters per workflow name.
    - up to 15
  How to map to WF:
  Clean Traffic Instance == SITE
  if "CHARTER" in details.get('Clean Traffic Instance ', '') or "Charter" in details.get('Clean Traffic Instance ', '') and details["ON DEMAND / AUTO-MITIGATE"] == "On Demand" and "CHTR" in details.get('CIRCUIT ID', ''):
      if po_create(customer_name, "WF_CHRT_COMM_MAN_FNM_CHRT"):
          created_pos.add(customer_name)
          for ip in details['IP Ranges']:
              add_network(customer_name, ip)
  
  elif "CHARTER" in details.get('Clean Traffic Instance ', '') or "Charter" in details.get('Clean Traffic Instance ', '') and details["ON DEMAND / AUTO-MITIGATE"] == "Auto Mitigate" and "CHTR" in details.get('CIRCUIT ID', ''):
      if po_create(customer_name, "WF_CHRT_COMM_AUT_FNM_CHRT"):
          created_pos.add(customer_name)
          for ip in details['IP Ranges']:
              add_network(customer_name, ip)
  
  elif "CHARTER" in details.get('Clean Traffic Instance ', '') or "Charter" in details.get('Clean Traffic Instance ', '') and details["ON DEMAND / AUTO-MITIGATE"] == "On Demand" and "TWCC" in details.get('CIRCUIT ID', ''):
      if po_create(customer_name, "WF_CHRT_COMM_MAN_FNM_TW"):
          created_pos.add(customer_name)
          for ip in details['IP Ranges']:
              add_network(customer_name, ip)
  
  elif "CHARTER" in details.get('Clean Traffic Instance ', '') or "Charter" in details.get('Clean Traffic Instance ', '') and details["ON DEMAND / AUTO-MITIGATE"] == "Auto Mitigate" and "TWCC" in details.get('CIRCUIT ID', ''):
      if po_create(customer_name, "WF_CHRT_COMM_AUT_FNM_TW"):
          created_pos.add(customer_name)
          for ip in details['IP Ranges']:
              add_network(customer_name, ip)
  
  elif "TWC" in details.get('Clean Traffic Instance ', '') and details["ON DEMAND / AUTO-MITIGATE"] == "On Demand" and "TWCC" in details.get('CIRCUIT ID', ''):
      if po_create(customer_name, "WF_TWC_COMM_MAN_FNM_TW"):
          created_pos.add(customer_name)
          for ip in details['IP Ranges']:
              add_network(customer_name, ip)
  
  elif "TWC" in details.get('Clean Traffic Instance ', '') and details["ON DEMAND / AUTO-MITIGATE"] == "Auto Mitigate" and "TWCC" in details.get('CIRCUIT ID', ''):
      if po_create(customer_name, "WF_TWC_COMM_AUT_FNM_TW"):
          created_pos.add(customer_name)
          for ip in details['IP Ranges']:
              add_network(customer_name, ip)
  
  elif "TWC" in details.get('Clean Traffic Instance ', '') and details["ON DEMAND / AUTO-MITIGATE"] == "On Demand" and "CHTR" in details.get('CIRCUIT ID', ''):
      if po_create(customer_name, "WF_TWC_COMM_MAN_FNM_CHRT"):
          created_pos.add(customer_name)
          for ip in details['IP Ranges']:
              add_network(customer_name, ip)
  
  elif "TWC" in details.get('Clean Traffic Instance ', '') and details["ON DEMAND / AUTO-MITIGATE"] == "Auto Mitigate" and "CHTR" in details.get('CIRCUIT ID', ''):
      if po_create(customer_name, "WF_TWC_COMM_AUT_FNM_CHRT"):
          created_pos.add(customer_name)
          for ip in details['IP Ranges']:
              add_network(customer_name, ip)
  
  
  Asset Settings - under CC configuration:
  ASSET SETTINGS ARE NOT EDITABLE WHEN ASSET IS ACTIVATED (ON CLOUD) with tooltip “On-cloud assets cannot be edited.”
  On Asset level settings → under Cyber Controller settings → bind from list of predefined workflows: WF can be edited and visiblie by OPERATOR ONLY => ACCOUNT AND ASSET ADMINS CANNOT VIEW (Operator Icon)
  - Enable setting of Asset thresholds per asset in the portal. (Account Admin/Asset Admin can view)
  - Thresholds are a single-select list bound to the asset:
  30Mbps
  50Mbps
  100Mbps
  200Mbps
  500Mbps
  1Gbps
  2Gbps
  5Gbps
  7Gbps
  10Gbps
  15Gbps
  25Gbps
  40Gbps
  Selected Line Speed (BW) determines the dedicated threshold template for that asset and can be edited.
  (based on the above settings use the provided .py file to create Confgiure Thresholds.)
  - add Circuit ID input on Asset level -:up to 100 chars [aA-zZ0-9_\.]  
  -  (Account Admin/Asset Admin can view)
  today in NOTES: 
  
  
  Current Behaviour and assumption (CHARTER)
  - Each PO today onboarded in Disabled” state new implementation is in Enabled by default.
    - Stateful → When creating PO in Enable state → PO will be configured in Flow Detector and upon failure can change to Disabled
    - need to check with or if need to scrape state Success/Failure  please check this
  - Detection
    - Detection is part of the predefined Workflow (WF) in CC.
    - Custom detections are predefined, with clear naming conventions (to be aligned with CHARTER).
  - Static Operations
    - Static operations such as divert/undivert test bypass the predefined CHARTER WF.
  - Asset ↔ PO binding
    - If Asset ID ≠ PO, Activate/Deactivate will not work.
    - Granular impact TBD
    - Each asset must have a fixed operation name bound to it.
  - When deleting an Account in the Unified Portal:
    - The related POs and configuration must also be deleted from CC.
  
  
  WILL BE MOVED TO NEXT PHASE: ----->>>>>>>>>>
  The Thresholds are View only for operator with customizations 
  
  Line Speed (which will result with dedicated threshold) 
  while custom config (in this example testlena): options for CHARTER:
  
  
  
  
  
  
  
  
  IGNORE:
  UI: instead of per SITE view in legacy:
  
  Move to Asset Setting level:
  
  add new section for “Protected Object” 
  
  Data Flow (DF) Configuration
  - DF settings must reflect PO onboarding logic.
  Collector Settings
  - Configure collectors if required (see screenshots for current setup).
  
  
  PO onboarding process:
  
  Today relevant Vision can be found per site (DF tag)
  *all SC in vision .13 except SJC vision .14

- **CDDOS-1875**: AI DOC Xpert - disclaimer | Ready for development | Inbal Reuven | 2025-12-23T14:51:42.179+0300
  AI DOC Xpert - disclaimer

- **CDDOS-1355**: Add to "Updates" link to survey monkey survey - add snack bar when new survey added | Pending UX Review | Inbal Reuven | 2025-12-23T14:43:23.164+0300
  Roi will check if we can do it this Q (efforts)

- **CDDOS-1567**: sdcc-status-aggregator | In Progress | Sergey Vlasov | 2025-12-23T13:11:41.858+0300
  current cycle ~ 60-80 sec
  should be 10-20 sec
  
  the main issue in aggregate assets ~ 70% from cycle
  - use only diverted assets
  - don’t find in DB per each asset, get from DB all assets records and store in dict
  - don’t save site object, useupdate with  $set for specific field

- **CDDOS-850**: Categorization of AI Crawlers/Bots and Analytics and Config Options for Customers | Done | Zohar Adir | 2025-12-22T16:13:23.703+0300
  Categorization of AI Crawlers/Bots and Analytics and Config Options for Customers

- **CDDOS-1855**: TLS Baselines widget | On Hold | Marom Duani Pe’er | 2025-12-22T14:33:22.164+0300
  TLS Baselines widget

- **CDDOS-1788**: Add acceptance for lets encrypt | On Hold | Marom Duani Pe’er | 2025-12-22T00:29:25.163+0300
  Add acceptance for lets encrypt

- **CDDOS-1781**: Bypass mTLS and Multi CA | Ready for QBR | Marom Duani Pe’er | 2025-12-22T00:28:52.550+0300
  Bypass mTLS and Multi CA

- **CDDOS-1874**: Filtering out Customer's device security events with the action of Forward not working correctly | Completed | Dani Gilboa | 2025-12-21T18:56:16.254+0300
  While attack service is successfully filtering out security events with action ‘Forward’ from Customer’s devices.
  Alert service which is responsible for notifications and should have the same filtering does not filter those security events, and sends notifications for security events that does not exist in the database

- **CDDOS-1582**: New marketplace agenda | In Progress | Inbal Reuven | 2025-12-21T11:40:28.595+0300
  create work plan-
    - work
  
   - figjam
  
  https://www.figma.com/make/hopU8BoxjlvAdthqaLqELV/Marketplace-Area-Development?node-id=0-1&t=mVbDCqdDmvvfUlHD-1 - make

- **CDDOS-1783**: CC+ - Sync allowlists/Block list on the fly  | Ready for development | Marom Duani Pe’er | 2025-12-21T10:31:51.428+0300
  CC+ - Sync allowlists/Block list on the fly

- **CDDOS-1873**: QA E2E Testing | In Progress | Karthik P | 2025-12-19T09:49:46.498+0300
  E2E Testing

- **CDDOS-1863**: QA: E2E Testing | In Progress | Karthik P | 2025-12-19T09:49:36.744+0300
  QA: E2E Testing

- **CDDOS-1801**: Policy editor - DNS Subdomains WL | On Hold | Inbal Reuven | 2025-12-18T20:11:18.054+0300
  Policy editor - DNS Subdomains WL

- **CDDOS-1814**: SOCX duplicated badges | In Progress | Unassigned | 2025-12-18T19:15:22.556+0300
  Exmple: SE CLOUD DEMO
  Hacme_92_61_238
  23/09/2025 23:22
  
  
  
  
  Additional issue → WAVE indexing is wrong. Attack with 2 waves showing WAVE 2 and WAVE 4

- **CDDOS-1872**: Status of protections and assigned asset are not visible for custom templates when upgrading account to the version 8.35 | To Do | Michael Blum | 2025-12-18T19:06:33.422+0300
  The status of protections and assigned assets is not visible for custom templates when upgrading the account to version 8.35.
  
  Steps to reproduce: 
  - Create default template
  - Create several custom templates
  Upgrade account to the DP version 8.35
  
  Result:
  The status of protections and assigned assets is not visible for custom templates when upgrading the account to version 8.35.
  
  
  Also status of protections and the assigned asset are not visible for a new custom template.

- **CDDOS-922**: Self Service Activate/Deactivate PO (Charter) + TCP option 28 | Done | Zohar Adir | 2025-12-18T16:39:44.710+0300
  Self Service Activate/Deactivate PO (Charter)

- **CDDOS-1861**: FE: Support new field for Granular IP address | Done | Lakshay J | 2025-12-18T13:42:09.567+0300
- **CDDOS-1869**: BE: Update Activate/Deactivate Logic - Blocker Service | Trash | Unassigned | 2025-12-18T13:41:43.665+0300
- **CDDOS-1868**: FE: Persist the changes in configuration | To-Do | Unassigned | 2025-12-18T13:41:28.345+0300
- **CDDOS-1457**: Import ACL to replace SSH sercvice | None | Venkatesh TL | 2025-12-18T11:44:24.459+0300
  Current FWaaS IP/Port filtering (Block, Process (new), Bypass) is managed via SSH commands and is error-prone (not scalable, fragile parsing, poor auth/audit, limited automation, unknown errors, multiple unnecessary commands).
  DP new version exposes native APIs enabling more efficient managment.
  Migrate FWaaS IP/Port filtering management from SSH to Import, preserving behavior and evaluation order while improving reliability, auditability, and automation.
  
  The URL: /dynamic/DefensePro/AccessControl/
  Import HLD TBD

- **CDDOS-1460**: SOCX Accuracy – Collecting Packet Size & Fragmentation&TTL Flags from NetFlow | None | Unassigned | 2025-12-18T11:35:13.431+0300
  Improve SOCX traffic feature accuracy by enriching flows with per-flow packet size distribution and fragmentation indicators, beyond today’s single average packet size.
  Current Gaps
  - Packet Size: only average size available → hides abnormal distributions, impossible to block attacks with clear Packet Size indication.
  - Fragmentation: no direct visibility, only weak inference (protocol=0).
  Feasibility via NetFlow/IPFIX
  - Packet Size:
    - Standard fields: octetDeltaCount + packetDeltaCount (→ average).
  - Fragmentation Flags:
    - IPFIX IE ipHeaderFlags (164) can export DF/MF bits.
    - *Some vendors also provide fragmentOffset (197) or expose it in ipHeaderPacketSection → we need to find a way to tag FRAG FLAG → More Flag (MF) in order to properly address the issue
    - In details:
      In NetFlow, we don’t detect fragmentation based on the fragment bits in the packet, because NetFlow doesn’t retain that information.
      Instead, we infer fragmentation when we see TCP or UDP traffic with source or destination port 0 — which typically appears starting from the second fragment, as the port information is only present in the first packet.
  - ipFragmentOffset
  - ipMoreFragments
  - ipFragmentFlags
  - fragmentIdentification
  - fragmentPacketCount
  Dependencies
  - Exporter templates must include these fields.
  - Collector (FNM) must parse and persist them in flow records.
  - SOCX must extend TF model to use these new features.
  Benefits for SOCX Improve clustering/classification accuracy by adding variance in packet size + frag indicators.
  - Verify field availability
  - Extend collector schema to parse packet length + ipHeaderFlags.
  - Feed enriched features to SOCX TF pipeline.

- **CDDOS-1816**: Statistics API returns incorrect comment timestamp when both from and to parameters are missing | Completed | Lakshay J | 2025-12-18T10:41:00.472+0300
  When calling the Traffic Statistics – Account API without from and to query parameters, the API should default to the current timestamp and return a clear comment with current timestamp in the response.
  Actual Behavior
  - When no from and to parameters are supplied:
    - The API returns a comment with a timestamp that does not match the expected current timestamp.
  Expected Behavior
  - If both from and to are missing:
    - The API should:
      - Use the current timestamp.
      - Return data for that 
        
        .

- **CDDOS-1815**: Statistics API incorrectly returns Comment for invalid time range (from > to) | Completed | Lakshay J | 2025-12-18T10:38:54.198+0300
  When calling the Traffic Statistics – Account API with time window where
  from > to, the API returns a response with the following comment:
  "comment": "Parameter \"from\" is greater than \"to\", data contains value at 1763650260"
  
  Given Data:
  from = 1763650260
  to   = 1763649360
  
  Expected Behavior
  According to the API design:
  - When from > to,
    the API should still return the From+1 min or first timestamp.
  - The expected timestamp should be:
  expected = from + 60 seconds  →  1763650260 + 60 = 1763650320

- **CDDOS-1866**: Activation/Deactivation changes | None | Unassigned | 2025-12-18T10:34:25.864+0300
  Activation and Deactivation changes

- **CDDOS-1871**: SupportAgent - New chat service (later Operator view with UI in unified) | None | Or Elazar | 2025-12-17T22:42:57.477+0300
  - Create new ChatGPT KEY with limited price.
  
  - Prompt guided Qs:
  - Serivce name or all portal?
  - Related to addon?
  - What is the prompt Err Msg?
  - Impact ALL customers?
  - who is the reporting Customer?
  - Describe the the SI and its impact.
  -  When reported?
  
  - SI Document schema:
  - id
  - submitter name
  - severity (CRITICAL if ALL services etc.)
  - CloudService
  - AddonName
  - ErrMsg
  - [GCPExcpetionLogRecord]
  - AllCustomers
  - CustomerName
  - SI Description
  - SI suggested Solution
  - SI mitigation steps list [action items]
  - R&D techy/architecture [R&D comment]
  - Date
  If no SI suggested solution or action items then status is still inquery…
  API for Known OnGoing SIs- list ALL of CURRENT OPEN SIs (those that are without solution/AIs.)
  
  - New service in mono-repo with CHAT Agent. (ref my “PSOC”)
  - Define Prompt: you are a SOC Expert advisor, consice, sharp and polite, with a bit sense of humour, with proficiency in the networking and cyber domains, specifically in Radware's DDOS, WAF and BOT services. 
  - Fetch products documentations as part of the db context if not already in Internet...
  - Upon query - prompt Qs, enrich, scan in SI DB, reply to chat.
  - Add menu for Operator view only for SI Agent usage.
  - P2: Add support for log/audit file upload and from it extract findings.

- **CDDOS-1870**: Reduce Account Sync - DDOS - use shared MongoDB vis Infrastructure service (rather than 1 account per 1 min API) | None | Or Elazar | 2025-12-17T22:26:58.437+0300
  services plan and traffic with CurGen should be fetched from DB rather then pull continually via REST API….
  suggested approach: Creating dedicate API in Infrastructure that knows to fetch from CurGen MongoDB.
  THIS CAN FURTHER be EXTENDED with SITEs and Asset views in unified (rather than portal APIs) at least for beginninng till unified will have those entities in its DB and own their responsibility.

- **CDDOS-1655**: DP 10 + DP8 Policy Editor Testing | In Progress | michaelsa | 2025-12-17T20:21:24.558+0300
  support for both dps with version 8(8.34/5...) and dp 10.
  CG side, policy editor side, blocker side , UI side and most importantly difference between devices.

- **CDDOS-1566**: sdcc-asset-advertisement-aggregator | Accepted | Sergey Vlasov | 2025-12-17T20:17:38.565+0300
  current cycle ~ 20-30 sec
  - check if ipnetwork is not used in loops
  - use bulk write as in site aggregator to avoid thousands od updates 
  - bgp_pending_assets = list(self._db.Asset.find({"status": Asset.STATUS_ON_CLOUD_BGP_PENDING})) - add projection
  expected cycle: ~ 5-10 sec

- **CDDOS-1850**: Consider removing Infrastructure service OR direct requests to it instead of RESTing CurGen | None | Or Elazar | 2025-12-17T17:23:03.266+0300
  if redundant entirely erase and set repllica 0.

- **CDDOS-1478**: SOCX Support Suspend action | Ready for development | Noy Cabel | 2025-12-17T16:49:34.950+0300
  SOCX Support Suspend action

- **CDDOS-1839**: 251211-000046 --Santander -- FWaaS does not disable geo blocking profile assigned to a single asset | Pending Verification | Lakshay J | 2025-12-17T16:43:46.945+0300
  Hi Team,
  We have an issue on FWaaS for tenants with just one asset and that have geo blocking rules.
  When we configure a geo blocking rule, we are asked to assign an asset to it.
  
  If we select 'All Assets', we are able to create another geo blocking rule for that one specific asset; and we can also enable it.
  
  However, when trying to disable the rule, we always get an error saying that the asset is part of the first rule (configured for All Assets).
  
   ,  
  Thank you for your help on session with Santander to disable the rule. We changed the flag from 'true' to 'false' on the database itself. This disabled the rule on portal; following which we used policy editor to push a dummy change that would remove geo blocking from all relevant DPs.
  Let me know if you need further information.
  The change we made today was for tenant - Santander, asset STN_195_234_141; policy editor template name - STN_195_234_141_1
  Thanks.

- **CDDOS-1798**: Radware Global Attack Insights (temp name) | In Progress | Linoy Moallem | 2025-12-17T16:20:33.814+0300
  Radware Global Attack Insights (temp name)

- **CDDOS-361**: SAaaS - Add-on service - AI SOCXpert | Done | Noy Cabel | 2025-12-17T16:06:59.130+0300
  SAaaS - Add-on service - AI SOCXpert

- **CDDOS-1867**: FE: Popup change to choose Entire Network or single network | To-Do | Unassigned | 2025-12-17T16:00:56.676+0300
- **CDDOS-881**: Telegram Claimed Attack Notification | Ready for development | Noy Cabel | 2025-12-17T16:00:48.399+0300
  Parent:

- **CDDOS-1858**: Support Granular Ip Address in Asset Settings | In Progress | Lakshay J | 2025-12-17T16:00:00.189+0300
  Support Granular Ip Address for Activation/Deactivation:
  - BE: Add new field to CyberControllerAssetSettings entity and Validate
  - BE: Pass new field as networks to the CC during activation/deactivation.
  - FE: Support new field for Granular IP address

- **CDDOS-1865**: CL Rule Save button remains disabled when try to adding an additional asset unless Port is specified Existing Rule | To Do | Venkatesh TL | 2025-12-17T15:38:49.697+0300
  When updating an existing CL rule to add an additional asset, the Save button does not get enabled.
  The Save button becomes enabled only after entering a Port value (e.g., any or a specific port).
  Observed behavior indicates that the Port field is implicitly set to 0, which prevents the Save action.
  
  Steps to Reproduce
  - Navigate to CL Rules.
  - Open an existing CL rule for edit.
  - Add one more asset to the rule.
  - Do not modify or enter any value in the Port field.
  - Observe the Save button state.
  
  Actual Result
  - Save button remains disabled
  - Port field internally holds value 0
  - Save button gets enabled only after manually entering Port = any or a valid port number
  
  Expected Result
  - Save button should be enabled after adding an asset.
  - Port field should either:
    - Default to any, or
  - Port value 0 should not block the Save operation

- **CDDOS-1819**: MSSP ROI Report  | None | Unassigned | 2025-12-17T12:08:52.353+0300
  1. Traffic Graph – Non-Technical Version
  1.1 Overall Goals
  - Help customers easily understand traffic patterns without technical terminology.
  - Clearly communicate whether an attack occurred, even if outside the default timeframe.
  - Reduce cognitive load through simplified labels, proactive cues, and clean formatting.
  
  1.2 When an Attack Has Occurred (any time in selected or broader window)
  Requirements
  - Attack Summary Header
    - Display a prominent header above the graph:
      - “Last DDoS attack occurred on MM/DD/YY.”
  - Proactive Hover Window
    - Automatically show the data hover panel on page load.
    - Include clear labeling and readable stats.
  
  1.3 When No Attack Exists Within Selected Timeframe
  Requirements
  - No-Attack Header
    - Display: “No attacks detected at this time.”
    - Subheader: “Use the drop-down on the right to adjust the timeframe.”
  - Proactive Hover Window
    - Auto-display hover panel.
  - Hover Window Title
    - Add a title explaining what the numbers represent (e.g., “Traffic details at selected time”).
  
  2. Status Summary (High-Level Health Overview)
  2.1 Goal
  Provide a clear, non-technical snapshot of the customer’s environment health to support internal communication.
  
  2.2 Summary Card – Part 1: Account Status Fields
  - Number of Assets
    - “X assets protected since MM/DD/YY.”
  - Current Status
    - Options:
      - “No attack”
      - “# of diversions initiated”
      - “# attacks mitigated”
  - Last Month
    - Same fields as above, with link to more attack details.
  - Last Six Months
    - Same fields, with link to attack details.
  
  2.3 Summary Card – Part 2: Your Insights
  When attacks occurred in last 6 months
  - Provide plain-language insight including:
    - Attack type(s)
    - Date and duration
    - How the attack was handled
    - Recommended next steps
    - Link to detailed attack reports
  When no attacks in last 6 months
  - Provide reassurance narrative including:
    - Number of packets inspected
    - Detection thresholds applied
    - Average attack frequency in the industry over this timeframe
    - Confirmation that traffic continues to be monitored
  
  2.4 Summary Card – Part 3: Monthly Stats
  - Protected bandwidth (e.g., 4 Gbps)
  - Assets (circuits) – purchased vs. used
  - Monitored traffic – typical and peak values
  
  2.5 Summary Card – Part 4: Your Settings
  - Protection plan (list available plans)
  - Protection type – Automated or Reactive
  - Detection threshold value
  - “More details” link → navigates to Asset Settings page
  
  3. Industry Insights - BE NEED TO BE ESTIMATED TRC?  your thoughts
  Goal
  Provide context by comparing the customer’s experience to trends in their sector.
  Requirements
  - Sector Attack Summary
    - Show number of attacks in this vertical over:
      - Last 2 weeks
      - Last 3 months
      - Last 6 months
  - Attack Types Breakdown
    - Summaries of common attack vectors in this industry.
  - Avg Downtime Impact
    - Non-technical, high-level estimate (hours or minutes).
  - Radware Performance Stats
    - Average time to detect
    - Average time to mitigate
  - UP SALE 
    - which feature is missing in order to mitigate this attack

- **CDDOS-1766**: Reduced LOGS ad support dynamic debug as needed per service via API | In Progress | Or Elazar | 2025-12-17T12:01:00.797+0300
  change for fixed time (3m?) the log level to debug . [ ideally with Kafka to all pods]
  OR 
  use the Spring Boot Actuator's /actuator/loggers endpoint and  management.endpoints.web.exposure.include=health,info,loggers
  Then the following (without AUTH header?) should work:
  curl -i -X POST -H "Content-Type: application/json" -d '{"configuredLevel": "INFO"}' http://localhost:8080/actuator/loggers/ROOT

- **CDDOS-22**: SOC-X - Auto Mitigation - Mitigation Action by User - Geo Filter | None | Unassigned | 2025-12-17T10:35:31.877+0300
  This Epic is the 2nd part of the SOC-X - User Mitigation Action, after we done the Traffic filter part 
   
  The purpose of this feature is to introduce a Temporarily Blocked Geolocation profile that applies across all Asset DP’s for dynamic and time-limited geo-based filtering.
  Key Definition:
  Independent from Regular FWaaS GEO Profiles – This protection operates separately from standard GEO filtering.
  - Available via SSH & Vision API – Managed through the geo-feed temporary-rules interface.
  - No Rule Limitations
  - Part of QA Cycle – This protection is included in validation and testing workflows.
  - Will be reset after Reboot
  - Security Events trap is similar to common protections:
  
  API for dynamic GEO rules only Disabled and BLOCK global actions:
  geo_prot_granular_DP10110 _v03_sep182025
  UI:
  Align with existing PE protections.
  Add an additional “GEO” Protection.
  - Visible only to operators and customers with the SOCX add-on (Operator icon):
  - Support country selection:
  
   
  CLI:
  - Supported Actions:
    - GET – Retrieve active rules.
    - DELETE – Remove specific blocked geolocations.
    - Not Supported: CREATE (rules must be added through predefined processes).
  - Example Command for Adding a Rule:
    dp geo-feed dynamic-rules add <policy name> <country> -d <blocking time-frame>
  - Time-Limited Blocking – Users can specify a duration for blocking.
  Naming & Event Handling
  - The rule is bind directly to Policy → no naming convention is required.
  User Interaction & Policy Management
  - From SecOps: Similar to TF rules, users can select, apply, and re-apply
  - From Policy Editor:similar to TF rule management.
  Acceptance Criteria
  - Geo rules are applied dynamically across all DP’s using the Temporarily Blocked Geolocation profile.
  - Independent operation from FWaaS GEO filtering.
  - Rules are accessible via SSH & Vision API with GET/DELETE actions.
  - Time-limited blocking is functional where applicable.
  - Naming convention follows SOCX-GEO format for easy identification.
  - Users can apply/revert rules via SecOps and delete rules via Policy Editor.

- **CDDOS-1609**: Live Chat Button | None | Zohar Adir | 2025-12-16T21:23:09.327+0300
  Live Chat button location is overlapping with other features “Apply” actions
  Figma

- **CDDOS-1757**: Make all Kafka Processors getTargetStream with try catch infra - change abstract and wrap the existing, TBD how to address errs/null values. | Trash | Or Elazar | 2025-12-16T18:19:27.209+0300
  public abstract KStream<_KEY, KValue> getTargetStream(KStream<KKey, KValue> flatSourceStream);
  Streams might throw exception if not only transformers (when complexed like audit/alert)... 
  If exception happens - it will re-inserted to the stream's topic infinitly.

- **CDDOS-1840**: CC Activate/Deactive Manual /32 diversion | In Progress | Linoy Moallem | 2025-12-16T17:23:53.031+0300
  CC Activate/Deactive Manual /32 diversion

- **CDDOS-1864**: Missing FE and BE validation for DNS Flood protection in DPX account template | To Do | Michael Blum | 2025-12-16T16:50:02.889+0300
  Missing FE and BE validation for DNS Flood protection in the DPX account template.
  When creating a custom account template for an asset diverted on DPX, the DNS Flood protection settings allow saving without a value for A Query.
  In the default template, this field is set to 90; however, in the custom template, it is empty.
  The template can be saved without this value, but the process will fail during policy import.
  How to reproduce
  - Create a custom account template for a DPX-diverted asset.
  - Enable protection DNS Flood, set Block and Report. (Do not open the menu to see the configuration)
  - Apply the changes without setting a value.
  Result:
  The import fails with the error: Failed to import policy with error: Content not found in the response

- **CDDOS-1773**: CC Activate/Deactive Manual /32 diversion | None | Venkatesh TL | 2025-12-16T16:41:23.236+0300
  Feature: On-Demand /32 Diversion (Subset of Asset Network)
  Goal: Allow diversion of a single /32 IP as a subset of an already-onboarded /24 asset network for TEST purposes
  Flow:
  - Under Asset Settings → Cyber controller settings
  - upon Granular activation → mandatory input
  - Input to enter a /32 IP address. “Enter IP Address for Diversion”
  - System validates that the entered /32 /128 belongs to the asset’s /24 network.
    - Upon save, If invalid → show error “Please enter an IP address that belongs to the asset network.”
  - On successful validation and Activation, only the specified /32 IP is diverted 
  
  On Asset level → Upon Activation click we need to have a pop-up option to select ALL or Granular divrsion → upon granular diversion selection → input IP (specific /32 /128) field):
  - Input: Granular flow
    - If the CC asset granular IP is empty → show an empty input field.
    - If the CC asset granular IP is set → show the prefilled input field with an option to edit.
    On submit:
    Update asset-level CC granular configuration:
    - If granular is not enabled → enable it and update the IP.
    - If ALL is selected → disable granular.
    UI behavior:
    - On hover over the Activate button → show the diverted IP at runtime.

- **CDDOS-1860**: BE: Pass new field as networks to the CC during activation/deactivation. | Done | Venkatesh TL | 2025-12-16T16:38:51.961+0300
- **CDDOS-1859**: BE: Add new field to CyberControllerAssetSettings entity and Validate | Done | Lakshay J | 2025-12-16T16:38:41.088+0300
- **CDDOS-1862**: Dev Testing: Integration and testing | In Progress | Lakshay J | 2025-12-16T16:38:30.258+0300
