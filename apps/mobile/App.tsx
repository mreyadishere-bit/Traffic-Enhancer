import React, { useCallback, useEffect, useState } from "react";
import { ActivityIndicator, ScrollView, StatusBar, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import * as DocumentPicker from "expo-document-picker";
import { File, Paths } from "expo-file-system";
import { fetch as expoFetch } from "expo/fetch";
import * as Sharing from "expo-sharing";

// Manual, foreground-only file import. Camera integration and true background
// queueing are NOT implemented. Never claim a recording was auto-transferred.
type Detection = { label: string; confidence: number };
type Incident = {
  id: string; filename: string; created_at: string; duration: number;
  sha256: string; status: string; error?: string | null;
  analysis?: {
    vehicle_detection?: { status: string; detections: Detection[] };
    transcription?: { status: string; text: string | null };
    plate_recognition?: { status: string };
    violation_assessment?: { status: string };
  } | null;
};
const BASE_BG = "#0c131c", PANEL = "#162530", CYAN = "#a9e8eb";
const formatTime = (s: string) => new Date(s).toLocaleString();
const message = (error: unknown) => error instanceof Error ? error.message : "Something went wrong";

function PrimaryButton({ text, onPress, disabled = false }: {text: string; onPress: () => void; disabled?: boolean}) {
  return <TouchableOpacity accessibilityRole="button" disabled={disabled} onPress={onPress} style={[styles.primary, disabled && styles.disabled]}><Text style={styles.primaryText}>{text}</Text></TouchableOpacity>;
}

export default function App() {
  const [baseUrl, setBaseUrl] = useState("");
  const [key, setKey] = useState("");
  const [connected, setConnected] = useState(false);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("Enter your development backend URL and operator key.");
  const [selectedVideo, setSelectedVideo] = useState<DocumentPicker.DocumentPickerAsset | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [focused, setFocused] = useState<string | null>(null);

  const cleanBase = baseUrl.trim().replace(/\/+$/, "");
  const request = useCallback(async (path: string, options: RequestInit = {}) => {
    if (!/^https?:\/\//.test(cleanBase)) throw new Error("Enter a complete http(s) API URL");
    const res = await fetch(cleanBase + "/api/v1" + path, {
      ...options,
      headers: { Authorization: "Bearer " + key, ...(options.headers || {}) },
    });
    if (!res.ok) {
      let detail = "Request failed: " + res.status;
      try { const body = await res.json(); if (typeof body.detail === "string") detail = body.detail; } catch {}
      throw new Error(detail);
    }
    return res;
  }, [cleanBase, key]);

  const refresh = useCallback(async () => {
    const res = await request("/incidents");
    const data = await res.json();
    setIncidents(data.items as Incident[]);
  }, [request]);

  async function connect() {
    setBusy(true);
    try { await refresh(); setConnected(true); setNotice("Connected to development API."); }
    catch (e) { setNotice("Connection failed: " + message(e)); }
    finally { setBusy(false); }
  }

  useEffect(() => {
    if (!connected || !incidents.some(x => x.status === "processing" || x.status === "queued")) return;
    const handle = setInterval(() => { refresh().catch(e => setNotice(message(e))); }, 3500);
    return () => clearInterval(handle);
  }, [connected, incidents, refresh]);

  async function pickVideo() {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: ["video/mp4", "video/quicktime", "video/x-matroska"],
        copyToCacheDirectory: true,
      });
      if (result.canceled || result.assets.length === 0) return;
      const asset = result.assets[0];
      if (!/\.(mp4|mov|mkv)$/i.test(asset.name)) {setNotice("Please select an MP4, MOV or MKV file."); return;}
      if (asset.size && asset.size > 150 * 1024 * 1024) {setNotice("File is larger than 150 MB."); return;}
      setSelectedVideo(asset); setNotice("Recording selected. Upload starts only when you tap Upload.");
    } catch (e) {setNotice("File picker: " + message(e));}
  }

  async function sendVideo() {
    if (!selectedVideo) return;
    setBusy(true); setNotice("Uploading selected recording while app is open…");
    try {
      const form = new FormData();
      form.append("video", new File(selectedVideo.uri), selectedVideo.name);
      const res = await expoFetch(cleanBase + "/api/v1/incidents", {
        method: "POST",
        headers: { Authorization: "Bearer " + key },
        body: form,
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || "Upload failed");
      setFocused(body.id); setSelectedVideo(null);
      setNotice("Evidence accepted by server. Refresh to follow actual processing status.");
      await refresh();
    } catch (e) {
      setNotice("Upload failed: " + message(e) + ". Check incident history before retrying.");
    } finally {setBusy(false);}
  }

  async function shareReport(id: string) {
    setBusy(true);
    try {
      const res = await request("/incidents/" + id + "/report.pdf");
      const pdf = new File(Paths.cache, "traffic-report-" + id + ".pdf");
      await pdf.write(await res.bytes());
      if (!(await Sharing.isAvailableAsync())) throw new Error("System sharing is not available");
      await Sharing.shareAsync(pdf.uri, { mimeType: "application/pdf", dialogTitle: "Export preliminary report" });
      setNotice("PDF exported to the system share sheet.");
    } catch (e) {setNotice("Report: " + message(e));}
    finally {setBusy(false);}
  }
  const current = incidents.find(x => x.id === focused) || null;

  return <SafeAreaProvider><SafeAreaView style={styles.safe}><StatusBar barStyle="light-content" />
    <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={styles.page}>
      <View style={styles.brand}><View style={styles.mark}><Text style={styles.markText}>TE</Text></View><View><Text style={styles.brandText}>TRAFFIC ENHANCER</Text><Text style={styles.brandCaption}>MOBILE EVIDENCE LAB · MVP</Text></View></View>
      <Text style={styles.overline}>INTELLIGENT ROAD SAFETY</Text>
      <Text style={styles.title}>Your evidence.{'\n'}<Text style={styles.accent}>Your clarity.</Text></Text>
      <Text style={styles.subtitle}>Import real footage, track processing and export preliminary findings.</Text>
      <View style={styles.notice}><Text style={styles.noticeText}>{notice}</Text></View>
      {!connected ? <View style={styles.card}>
        <Text style={styles.cardEyebrow}>CONNECT TO LOCAL DEVELOPMENT API</Text>
        <Text style={styles.label}>Backend URL (HTTPS recommended)</Text>
        <TextInput value={baseUrl} onChangeText={setBaseUrl} placeholder="https://your-test-api.example" placeholderTextColor="#758f9b" keyboardType="url" autoCapitalize="none" autoCorrect={false} style={styles.input}/>
        <Text style={styles.label}>Temporary operator key</Text>
        <TextInput value={key} onChangeText={setKey} placeholder="TE_API_KEY" placeholderTextColor="#758f9b" secureTextEntry autoCapitalize="none" style={styles.input}/>
        <PrimaryButton text={busy ? "Connecting…" : "Connect to API ↗"} onPress={connect} disabled={busy || !key || !baseUrl}/>
        <Text style={styles.hint}>The key is held in memory only. Local API port 127.0.0.1 is not reachable from a separate physical phone. Do not use this development token for production accounts.</Text>
      </View> : <>
        <View style={styles.metrics}><View style={styles.metric}><Text style={styles.cardEyebrow}>INCIDENTS</Text><Text style={styles.number}>{incidents.length}</Text></View><View style={styles.metric}><Text style={styles.cardEyebrow}>READY</Text><Text style={styles.number}>{incidents.filter(x=>x.status==="ready").length}</Text></View></View>
        <View style={styles.card}><Text style={styles.cardEyebrow}>01 / EVIDENCE IMPORT</Text><Text style={styles.cardTitle}>Bring a recording in.</Text>
          <Text style={styles.paragraph}>Files / manufacturer-shared video. No automatic camera discovery or background transfer is available in this build.</Text>
          <TouchableOpacity onPress={pickVideo} style={styles.picker}><Text style={styles.pickerIcon}>↑</Text><Text style={styles.pickerText}>{selectedVideo?.name || "Choose video from Files"}</Text><Text style={styles.hint}>MP4 / MOV / MKV · maximum 150 MB</Text></TouchableOpacity>
          <PrimaryButton text={busy ? "Working…" : "Upload evidence ↗"} onPress={sendVideo} disabled={!selectedVideo || busy}/>
        </View>
        <View style={styles.card}><View style={styles.row}><Text style={styles.cardEyebrow}>02 / INCIDENT HISTORY</Text><TouchableOpacity accessibilityRole="button" onPress={()=>refresh().catch(e=>setNotice(message(e)))}><Text style={styles.refresh}>Refresh ↻</Text></TouchableOpacity></View>
          {incidents.length===0 ? <Text style={styles.paragraph}>No evidence has been uploaded yet.</Text> : incidents.map(item=><TouchableOpacity key={item.id} onPress={()=>setFocused(item.id)} style={[styles.incident, focused===item.id && styles.focused]}>
            <View style={styles.row}><Text numberOfLines={1} style={styles.incidentName}>{item.filename}</Text><Text style={styles.status}>{item.status.toUpperCase()}</Text></View>
            <Text style={styles.hint}>{formatTime(item.created_at)} · {item.duration.toFixed(1)} seconds</Text>
          </TouchableOpacity>)}
        </View>
        {current && <View style={styles.card}><Text style={styles.cardEyebrow}>03 / PRELIMINARY REPORT</Text><Text style={styles.cardTitle}>{current.filename}</Text>
          <Text style={styles.paragraph}>Status: {current.status}. Vehicle detection: {current.analysis?.vehicle_detection?.status || "not available"}.</Text>
          <Text style={styles.paragraph}>Speech: {current.analysis?.transcription?.text || "No transcription available"}</Text>
          <Text style={styles.hint}>Never interpret preliminary AI findings as a confirmed violation. Original SHA-256: {current.sha256}</Text>
          <PrimaryButton text={busy ? "Working…" : "Export PDF report ↓"} onPress={()=>shareReport(current.id)} disabled={busy || current.status!=="ready"}/>
        </View>}
        <TouchableOpacity accessibilityRole="button" style={styles.disconnect} onPress={()=>{setConnected(false);setKey("");setIncidents([]);setFocused(null);setNotice("Disconnected. Operator key cleared.");}}><Text style={styles.disconnectText}>Disconnect and clear key</Text></TouchableOpacity>
      </>}
      <Text style={styles.footer}>NO VERIFIED ENFORCEMENT · ANDROID + iOS DEVELOPMENT MVP</Text>
    </ScrollView>
    {busy && <View pointerEvents="none" style={styles.spinner}><ActivityIndicator size="small" color={CYAN}/></View>}
  </SafeAreaView></SafeAreaProvider>;
}
const styles = StyleSheet.create({
 safe:{flex:1,backgroundColor:BASE_BG},page:{paddingHorizontal:23,paddingTop:19,paddingBottom:46},
 brand:{flexDirection:"row",alignItems:"center",gap:12,marginBottom:40},
 mark:{width:43,height:43,backgroundColor:CYAN,borderRadius:12,alignItems:"center",justifyContent:"center"},markText:{fontWeight:"900",color:"#102b32",fontSize:16},
 brandText:{color:"#edf8f8",fontSize:13,fontWeight:"800",letterSpacing:1.3},brandCaption:{fontSize:9,color:"#86a1ae",letterSpacing:1.5,marginTop:5},
 overline:{fontSize:10,color:"#9bd9e1",fontWeight:"800",letterSpacing:2.1,marginBottom:14},
 title:{fontSize:38,fontWeight:"700",letterSpacing:-1.5,color:"#f0f7f8",lineHeight:44},accent:{color:CYAN},
 subtitle:{fontSize:13,color:"#94a9b4",lineHeight:21,marginTop:13,marginBottom:22},
 notice:{backgroundColor:"#19323c",borderColor:"#335a66",borderWidth:1,borderRadius:9,padding:13,marginBottom:18},
 noticeText:{color:"#b6dcdf",fontSize:12,lineHeight:19},
 card:{backgroundColor:PANEL,borderColor:"#2a424f",borderWidth:1,borderRadius:13,padding:21,marginBottom:15},
 cardEyebrow:{color:"#91cbd3",fontWeight:"800",letterSpacing:1.4,fontSize:10,marginBottom:14},
 cardTitle:{color:"#eef8f9",fontWeight:"750",fontSize:19,letterSpacing:-.45,marginBottom:11},
 label:{fontSize:11,color:"#9cb2be",fontWeight:"750",marginBottom:8},
 input:{borderWidth:1,borderColor:"#3b5b68",backgroundColor:"#0e1c25",borderRadius:8,color:"#f0fafb",paddingHorizontal:14,paddingVertical:13,marginBottom:17,fontSize:13},
 primary:{backgroundColor:CYAN,borderRadius:8,justifyContent:"center",alignItems:"center",paddingVertical:16,marginTop:8},primaryText:{color:"#12303a",fontSize:13,fontWeight:"850"},
 disabled:{opacity:.4},hint:{color:"#799aa7",fontSize:10,lineHeight:17,marginTop:12},paragraph:{color:"#a0b6be",fontSize:12,lineHeight:19,marginBottom:15},
 metrics:{flexDirection:"row",gap:11,marginBottom:14},metric:{backgroundColor:PANEL,flex:1,borderColor:"#29414e",borderWidth:1,borderRadius:11,padding:18},number:{fontSize:33,color:"#ecf5f7",fontWeight:"750"},
 picker:{borderWidth:1,borderStyle:"dashed",borderColor:"#5a8590",borderRadius:10,alignItems:"center",padding:24,backgroundColor:"#182d38",marginBottom:12},
 pickerIcon:{fontSize:33,color:CYAN},pickerText:{color:"#e1f4f5",fontWeight:"700",fontSize:13,marginTop:9,textAlign:"center"},
 row:{flexDirection:"row",alignItems:"center",justifyContent:"space-between",gap:10},refresh:{fontSize:12,color:CYAN},
 incident:{padding:14,borderColor:"#314b58",borderWidth:1,borderRadius:8,marginTop:9,backgroundColor:"#12242f"},
 focused:{borderColor:CYAN},incidentName:{fontSize:12,fontWeight:"700",color:"#e4f3f5",maxWidth:170},status:{fontSize:9,color:"#b2e5cb",fontWeight:"800"},
 disconnect:{alignItems:"center",padding:16,marginBottom:17},disconnectText:{fontSize:12,color:"#94b4bd"},
 footer:{textAlign:"center",fontSize:9,color:"#708e9a",letterSpacing:.8},
 spinner:{position:"absolute",right:16,top:14}
});
