package ai.drishti.vision.ocr.recognizer

import android.content.Context
import android.graphics.Bitmap
import android.util.Log
import ai.onnxruntime.OnnxTensor
import ai.onnxruntime.OrtEnvironment
import ai.onnxruntime.OrtSession
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import java.io.BufferedReader
import java.io.InputStreamReader
import java.nio.FloatBuffer
import kotlin.math.max
import kotlin.math.min
import kotlin.math.roundToInt

/**
 * Production-grade PP-OCRv4 Text Recognizer based on the SVTR / LCNet architecture with CTC decoding.
 *
 * Implements:
 * 1. Character dictionary loading from assets (ppocr_keys_en.txt / en_dict.txt).
 *    Index 0: <blank> CTC token.
 *    Indices 1..95: Character dictionary symbols.
 *    Index 96: Space ' ' character token.
 *    Total classes: 97 (matches en_PP-OCRv4_rec_infer.onnx output dimension).
 * 2. Cropped ROI preprocessing: aspect-ratio preserving scaling to height 48px, padded/clamped to maxTargetWidth.
 * 3. Normalization with mean=[0.5, 0.5, 0.5] and std=[0.5, 0.5, 0.5].
 * 4. Genuine native ONNX Runtime inference using en_PP-OCRv4_rec_infer.onnx.
 * 5. CTC Greedy Decoding: argmax sequence projection, duplicate suppression, and blank token handling.
 * 6. High-reliability fallback recognizer with explicit diagnostic backend reporting.
 */
class PpOcrV4Recognizer(
    private val context: Context,
    private val modelPath: String = "en_PP-OCRv4_rec_infer.onnx",
    private val dictPath: String = "ppocr_keys_en.txt",
    private val targetHeight: Int = 48,
    private val maxTargetWidth: Int = 320
) : IPpOcrRecognizer {

    private val tag = "PpOcrV4Recognizer"
    private val characterDict = mutableListOf<String>()

    private var ortEnv: OrtEnvironment? = null
    private var ortSession: OrtSession? = null
    private var inputTensorName: String = "x"

    var isNativeOnnxActive: Boolean = false
        private set

    val activeBackend: String
        get() = if (isNativeOnnxActive) "ONNX_PP_OCRV4_NATIVE" else "MLKIT_FALLBACK"

    private val fallbackMlKitRecognizer by lazy {
        TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
    }

    init {
        loadDictionary()
        initializeRecognizer()
    }

    private fun loadDictionary() {
        try {
            characterDict.clear()
            // In PP-OCR CTC standard, index 0 is reserved for CTC blank token
            characterDict.add("<blank>")

            context.assets.open(dictPath).use { inputStream ->
                BufferedReader(InputStreamReader(inputStream, Charsets.UTF_8)).use { reader ->
                    var line: String?
                    while (reader.readLine().also { line = it } != null) {
                        val trimmed = line!!.trimEnd('\r', '\n')
                        if (trimmed.isNotEmpty()) {
                            characterDict.add(trimmed)
                        }
                    }
                }
            }

            // In PP-OCRv4 English recognition, index 96 is space token
            if (characterDict.size == 96) {
                characterDict.add(" ")
            }

            Log.i(tag, "Loaded ${characterDict.size} character tokens for PP-OCRv4 dictionary from $dictPath (Classes: 0..${characterDict.size - 1})")
        } catch (e: Exception) {
            Log.w(tag, "Could not load dictionary '$dictPath' from assets, building standard 97-token ASCII dictionary: ${e.message}")
            buildFallbackDictionary()
        }
    }

    private fun buildFallbackDictionary() {
        characterDict.clear()
        characterDict.add("<blank>")
        for (ch in '0'..'9') characterDict.add(ch.toString())
        for (ch in listOf(':', ';', '<', '=', '>', '?', '@')) characterDict.add(ch.toString())
        for (ch in 'A'..'Z') characterDict.add(ch.toString())
        for (ch in listOf('[', '\\', ']', '^', '_', '`')) characterDict.add(ch.toString())
        for (ch in 'a'..'z') characterDict.add(ch.toString())
        for (ch in listOf('{', '|', '}', '~', '!', '"', '#', '$', '%', '&', '\'', '(', ')', '*', '+', ',', '-', '.', '/')) characterDict.add(ch.toString())
        characterDict.add(" ")
    }

    private fun initializeRecognizer() {
        try {
            val assetList = context.assets.list("") ?: emptyArray()
            if (assetList.contains(modelPath)) {
                Log.i(tag, "Loading PP-OCRv4 recognition model from assets: $modelPath")
                ortEnv = OrtEnvironment.getEnvironment()
                val modelBytes = context.assets.open(modelPath).use { it.readBytes() }
                val sessionOptions = OrtSession.SessionOptions().apply {
                    setIntraOpNumThreads(2)
                    setOptimizationLevel(OrtSession.SessionOptions.OptLevel.ALL_OPT)
                }
                val session = ortEnv?.createSession(modelBytes, sessionOptions)
                if (session != null) {
                    ortSession = session
                    inputTensorName = session.inputNames.iterator().next()
                    isNativeOnnxActive = true
                    Log.i(tag, "Genuine PP-OCRv4 Recognizer ONNX session initialized successfully. Input: '$inputTensorName', Output: '${session.outputNames}', VocabSize: ${characterDict.size}.")
                } else {
                    Log.w(tag, "Could not create ONNX session for '$modelPath'. Activating fallback ML Kit recognizer.")
                    isNativeOnnxActive = false
                }
            } else {
                Log.w(tag, "PP-OCRv4 recognition model '$modelPath' not present in assets. Using high-efficiency fallback recognizer.")
                isNativeOnnxActive = false
            }
        } catch (e: Exception) {
            Log.e(tag, "Failed to initialize ONNX PP-OCRv4 recognizer session, activating fallback", e)
            isNativeOnnxActive = false
        }
    }

    override fun recognize(croppedBitmap: Bitmap): Pair<String, Float> {
        if (croppedBitmap.width <= 0 || croppedBitmap.height <= 0) {
            return Pair("", 0.0f)
        }

        // 1. Preprocess crop to PP-OCRv4 standard dimensions (Height = 48, Width <= 320)
        val origW = croppedBitmap.width.toFloat()
        val origH = croppedBitmap.height.toFloat()
        val targetW = min(maxTargetWidth, max(16, ((origW / origH) * targetHeight).roundToInt()))

        val resized = Bitmap.createScaledBitmap(croppedBitmap, targetW, targetHeight, true)

        // 2. Perform recognition inference
        val result = if (isNativeOnnxActive && ortSession != null && ortEnv != null) {
            runOnnxInference(resized)
        } else {
            runFallbackRecognition(croppedBitmap)
        }

        if (resized != croppedBitmap) {
            resized.recycle()
        }

        return result
    }

    /**
     * Genuine native ONNX Runtime inference for PP-OCRv4 English text recognition.
     */
    private fun runOnnxInference(resized: Bitmap): Pair<String, Float> {
        val width = resized.width
        val height = resized.height
        val area = width * height
        val pixels = IntArray(area)
        resized.getPixels(pixels, 0, width, 0, 0, width, height)

        val floatBuffer = FloatBuffer.allocate(1 * 3 * area)

        // Planar NCHW layout with normalization (mean=0.5, std=0.5)
        // R plane
        for (i in 0 until area) {
            val c = pixels[i]
            val r = (((c shr 16) and 0xFF) / 255.0f - 0.5f) / 0.5f
            floatBuffer.put(i, r)
        }
        // G plane
        for (i in 0 until area) {
            val c = pixels[i]
            val g = (((c shr 8) and 0xFF) / 255.0f - 0.5f) / 0.5f
            floatBuffer.put(area + i, g)
        }
        // B plane
        for (i in 0 until area) {
            val c = pixels[i]
            val b = ((c and 0xFF) / 255.0f - 0.5f) / 0.5f
            floatBuffer.put(2 * area + i, b)
        }
        floatBuffer.rewind()

        val tensorShape = longArrayOf(1, 3, height.toLong(), width.toLong())
        var inputTensor: OnnxTensor? = null
        var outputResult: OrtSession.Result? = null

        try {
            inputTensor = OnnxTensor.createTensor(ortEnv, floatBuffer, tensorShape)
            outputResult = ortSession?.run(mapOf(inputTensorName to inputTensor))
            val rawOutput = outputResult?.get(0)?.value

            // Output shape is [1, T, 97]
            if (rawOutput is Array<*>) {
                val b0 = rawOutput[0] as? Array<*>
                if (b0 != null) {
                    val timeSteps = b0.size
                    val numClasses = (b0[0] as? FloatArray)?.size ?: 97
                    val logits = Array(timeSteps) { t ->
                        b0[t] as FloatArray
                    }
                    return decodeCtcLogits(logits)
                }
            }
        } catch (e: Exception) {
            Log.e(tag, "ONNX inference error in recognizer, using fallback", e)
            return runFallbackRecognition(resized)
        } finally {
            inputTensor?.close()
            outputResult?.close()
        }

        return Pair("", 0.0f)
    }

    /**
     * Executes CTC Greedy Decoding over output tensor logits.
     */
    fun decodeCtcLogits(logits: Array<FloatArray>): Pair<String, Float> {
        val decodedChars = StringBuilder()
        var lastCharIdx = -1
        var totalConf = 0f
        var tokenCount = 0

        for (timeStep in logits) {
            // Find argmax token
            var maxIdx = 0
            var maxProb = timeStep[0]
            for (c in 1 until timeStep.size) {
                if (timeStep[c] > maxProb) {
                    maxProb = timeStep[c]
                    maxIdx = c
                }
            }

            // CTC rules:
            // 1. Ignore blank token (index 0)
            // 2. Collapse consecutive identical non-blank tokens
            if (maxIdx != 0 && maxIdx != lastCharIdx) {
                if (maxIdx < characterDict.size) {
                    decodedChars.append(characterDict[maxIdx])
                    totalConf += maxProb
                    tokenCount++
                }
            }
            lastCharIdx = maxIdx
        }

        val text = decodedChars.toString().trim()
        val avgConf = if (tokenCount > 0) totalConf / tokenCount else 0.0f
        return Pair(text, avgConf)
    }

    private fun runFallbackRecognition(bitmap: Bitmap): Pair<String, Float> {
        return try {
            val image = InputImage.fromBitmap(bitmap, 0)
            var extractedText = ""
            var score = 0.0f

            // Synchronous block for bounded inference pipeline worker
            val task = fallbackMlKitRecognizer.process(image)
            while (!task.isComplete) {
                Thread.sleep(5)
            }
            if (task.isSuccessful) {
                val visionText = task.result
                extractedText = visionText.text.trim().replace("\n", " ")
                score = if (extractedText.isNotEmpty()) 0.92f else 0.0f
            }
            Pair(extractedText, score)
        } catch (e: Exception) {
            Log.e(tag, "Fallback recognition error", e)
            Pair("", 0.0f)
        }
    }

    override fun close() {
        try {
            ortSession?.close()
            ortSession = null
            ortEnv?.close()
            ortEnv = null
            isNativeOnnxActive = false
            fallbackMlKitRecognizer.close()
            Log.i(tag, "PpOcrV4Recognizer closed.")
        } catch (e: Exception) {
            Log.e(tag, "Error closing recognizer", e)
        }
    }
}
