package com.v.tts

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.Bundle
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.*

/**
 * Main Activity for V-TTS Demo.
 */
class MainActivity : AppCompatActivity() {
    
    private lateinit var textInput: EditText
    private lateinit var speakerSpinner: Spinner
    private lateinit var synthesizeButton: Button
    private lateinit var statusText: TextView
    private lateinit var progressBar: ProgressBar
    private lateinit var audioControls: android.widget.LinearLayout
    private lateinit var replayButton: Button
    private lateinit var audioDuration: TextView
    
    private var ttsEngine: VTTSEngine? = null
    private var audioTrack: AudioTrack? = null
    private var isInitialized = false
    private var lastAudioData: FloatArray? = null  // Store last audio for replay
    
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        
        // Initialize views
        textInput = findViewById(R.id.textInput)
        speakerSpinner = findViewById(R.id.speakerSpinner)
        synthesizeButton = findViewById(R.id.synthesizeButton)
        statusText = findViewById(R.id.statusText)
        progressBar = findViewById(R.id.progressBar)
        audioControls = findViewById(R.id.audioControls)
        replayButton = findViewById(R.id.replayButton)
        audioDuration = findViewById(R.id.audioDuration)
        
        // Setup spinner with 5 voices
        val speakers = arrayOf(
            "NF - Northern Female (Bắc Nữ)",
            "SF - Southern Female (Nam Nữ)", 
            "NM1 - Northern Male 1 (Bắc Nam 1)",
            "SM - Southern Male (Nam Nam)",
            "NM2 - Northern Male 2 (Bắc Nam 2)"
        )
        speakerSpinner.adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, speakers)
        
        // Setup buttons
        synthesizeButton.setOnClickListener {
            synthesize()
        }
        synthesizeButton.isEnabled = false
        
        replayButton.setOnClickListener {
            lastAudioData?.let { audio ->
                playAudio(audio, VTTSEngine.SAMPLE_RATE)
                statusText.text = "🔊 Đang phát lại..."
            }
        }
        
        // Default text
        textInput.setText("Xin chào, chúc bạn một ngày tốt lành")
        
        // Initialize TTS engine
        initializeEngine()
    }
    
    private fun initializeEngine() {
        statusText.text = "🔄 Đang tải models..."
        progressBar.visibility = android.view.View.VISIBLE
        
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                ttsEngine = VTTSEngine(this@MainActivity)
                ttsEngine?.initialize()
                
                withContext(Dispatchers.Main) {
                    isInitialized = true
                    synthesizeButton.isEnabled = true
                    progressBar.visibility = android.view.View.GONE
                    statusText.text = "✅ Sẵn sàng"
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    progressBar.visibility = android.view.View.GONE
                    statusText.text = "❌ Lỗi: ${e.message}"
                    android.util.Log.e("MainActivity", "Init error", e)
                }
            }
        }
    }
    
    private fun synthesize() {
        val text = textInput.text.toString().trim()
        if (text.isEmpty()) {
            statusText.text = "⚠️ Vui lòng nhập văn bản"
            return
        }
        
        if (!isInitialized) {
            statusText.text = "⚠️ Đang tải models..."
            return
        }
        
        // Speaker ID: 0=NF, 1=SF, 2=NM1, 3=SM, 4=NM2
        val speakerId = speakerSpinner.selectedItemPosition
        
        synthesizeButton.isEnabled = false
        progressBar.visibility = android.view.View.VISIBLE
        statusText.text = "🔄 Đang tạo giọng nói..."
        
        lifecycleScope.launch(Dispatchers.IO) {
            try {
                val startTime = System.currentTimeMillis()
                
                val audio = ttsEngine?.synthesize(
                    text = text,
                    speakerId = speakerId
                ) ?: throw Exception("TTS engine not initialized")
                
                val duration = (System.currentTimeMillis() - startTime) / 1000.0
                val audioDurationSecs = audio.size.toFloat() / VTTSEngine.SAMPLE_RATE
                
                withContext(Dispatchers.Main) {
                    lastAudioData = audio  // Store for replay
                    playAudio(audio, VTTSEngine.SAMPLE_RATE)
                    progressBar.visibility = android.view.View.GONE
                    statusText.text = "✅ Đã tạo ${audio.size} samples (${String.format("%.2f", duration)}s)"
                    synthesizeButton.isEnabled = true
                    
                    // Show audio controls
                    audioControls.visibility = android.view.View.VISIBLE
                    audioDuration.text = "⏱️ ${String.format("%.1f", audioDurationSecs)}s"
                }
            } catch (e: Exception) {
                withContext(Dispatchers.Main) {
                    progressBar.visibility = android.view.View.GONE
                    statusText.text = "❌ Lỗi: ${e.message}"
                    synthesizeButton.isEnabled = true
                    android.util.Log.e("MainActivity", "Synthesis error", e)
                }
            }
        }
    }
    
    private fun playAudio(audioData: FloatArray, sampleRate: Int) {
        // Convert float to short
        val shortData = ShortArray(audioData.size) { i ->
            (audioData[i] * 32767).toInt().coerceIn(-32768, 32767).toShort()
        }
        
        audioTrack?.release()
        
        audioTrack = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .build()
            )
            .setBufferSizeInBytes(shortData.size * 2)
            .setTransferMode(AudioTrack.MODE_STATIC)
            .build()
        
        audioTrack?.write(shortData, 0, shortData.size)
        audioTrack?.play()
    }
    
    override fun onDestroy() {
        super.onDestroy()
        audioTrack?.release()
        ttsEngine?.close()
    }
}
