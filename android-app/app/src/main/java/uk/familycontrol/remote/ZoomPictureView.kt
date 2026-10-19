package uk.familycontrol.remote

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.graphics.RectF
import android.view.MotionEvent
import android.view.ScaleGestureDetector
import android.widget.ImageView

/** In-app fullscreen screenshot preview with pinch-to-zoom and dragging. */
class ZoomPictureView(context: Context) : ImageView(context) {
    private val transform = Matrix()
    private var picture: Bitmap? = null
    private var activeScale = 1f
    private var xBefore = 0f
    private var yBefore = 0f
    private val gestures = ScaleGestureDetector(context,
        object : ScaleGestureDetector.SimpleOnScaleGestureListener() {
            override fun onScale(detector: ScaleGestureDetector): Boolean {
                zoom(detector.scaleFactor, detector.focusX, detector.focusY)
                return true
            }
        })

    init {
        scaleType = ScaleType.MATRIX
        setBackgroundColor(android.graphics.Color.BLACK)
    }

    fun setPicture(bitmap: Bitmap) {
        picture = bitmap
        setImageBitmap(bitmap)
        post { fit() }
    }

    fun fit() {
        val bitmap = picture ?: return
        if (width < 1 || height < 1) return
        transform.reset()
        val image = RectF(0f, 0f, bitmap.width.toFloat(), bitmap.height.toFloat())
        val screen = RectF(0f, 0f, width.toFloat(), height.toFloat())
        transform.setRectToRect(image, screen, Matrix.ScaleToFit.CENTER)
        activeScale = 1f
        imageMatrix = transform
        invalidate()
    }

    fun zoom(factor: Float, x: Float = width / 2f, y: Float = height / 2f) {
        val change = factor.coerceIn(0.5f, 2f)
        val next = (activeScale * change).coerceIn(1f, 8f)
        val actual = next / activeScale
        activeScale = next
        transform.postScale(actual, actual, x, y)
        imageMatrix = transform
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        gestures.onTouchEvent(event)
        if (event.pointerCount == 1) {
            when (event.actionMasked) {
                MotionEvent.ACTION_DOWN -> {
                    xBefore = event.x
                    yBefore = event.y
                    return true
                }
                MotionEvent.ACTION_MOVE -> {
                    if (!gestures.isInProgress && activeScale > 1f) {
                        transform.postTranslate(event.x - xBefore, event.y - yBefore)
                        imageMatrix = transform
                    }
                    xBefore = event.x
                    yBefore = event.y
                    return true
                }
            }
        }
        return true
    }

    override fun onSizeChanged(w: Int, h: Int, oldw: Int, oldh: Int) {
        super.onSizeChanged(w, h, oldw, oldh)
        post { fit() }
    }
}
