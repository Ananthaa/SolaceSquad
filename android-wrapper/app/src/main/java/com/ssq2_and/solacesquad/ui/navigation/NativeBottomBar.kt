package com.ssq2_and.solacesquad.ui.navigation

import android.view.HapticFeedbackConstants
import androidx.compose.animation.*
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bolt
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.MedicalServices
import androidx.compose.material.icons.filled.Person
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

import androidx.compose.material.icons.filled.Favorite
import androidx.compose.material.icons.filled.MedicalServices

enum class TabItem(val title: String, val path: String, val icon: ImageVector) {
    HOME("Home", "/user-dashboard", Icons.Default.Home),
    VITALS("Vital Scan", "/vitals", Icons.Default.Favorite),
    QUICK_CONSULT("Quick Consult", "/quick-consult-web", Icons.Default.Bolt),
    CONSULT("Book Consult", "/consultants", Icons.Default.MedicalServices),
    PROFILE("Profile", "/app/profile", Icons.Default.Person);

    companion object {
        fun fromUrl(url: String): TabItem {
            val lower = url.lowercase()
            return when {
                lower.contains("quick-consult") || lower.contains("quickconsult") -> QUICK_CONSULT
                lower.contains("vitals") -> VITALS
                lower.contains("consultant") -> CONSULT
                lower.contains("profile") -> PROFILE
                lower.contains("dashboard") || lower.contains("/app") -> HOME
                else -> HOME
            }
        }

        fun isAuthOrCallRoom(url: String): Boolean {
            val lower = url.lowercase()
            return lower.contains("login") ||
                   lower.contains("signup") ||
                   lower.contains("reset_password") ||
                   lower.contains("forgot-password") ||
                   lower.contains("call_room") ||
                   lower.contains("call-room") ||
                   lower.contains("quick-consult/room")
        }
    }
}

val TealPrimary = Color(0xFF0D9488)
val TealDark = Color(0xFF0F766E)
val InactiveGray = Color(0xFF94A3B8)

@Composable
fun NativeBottomBar(
    selectedTab: TabItem,
    onTabSelected: (TabItem) -> Unit,
    isVisible: Boolean,
    modifier: Modifier = Modifier
) {
    val view = LocalView.current

    AnimatedVisibility(
        visible = isVisible,
        enter = slideInVertically(initialOffsetY = { it }) + fadeIn(),
        exit = slideOutVertically(targetOffsetY = { it }) + fadeOut(),
        modifier = modifier
    ) {
        Surface(
            modifier = Modifier
                .fillMaxWidth()
                .shadow(elevation = 12.dp, spotColor = Color.Black.copy(alpha = 0.15f)),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 3.dp
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(horizontal = 4.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.SpaceAround,
                verticalAlignment = Alignment.CenterVertically
            ) {
                // Tab 1: Home
                TabButton(
                    tab = TabItem.HOME,
                    isSelected = selectedTab == TabItem.HOME,
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                        onTabSelected(TabItem.HOME)
                    },
                    modifier = Modifier.weight(1f)
                )

                // Tab 2: Vital Scan
                TabButton(
                    tab = TabItem.VITALS,
                    isSelected = selectedTab == TabItem.VITALS,
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                        onTabSelected(TabItem.VITALS)
                    },
                    modifier = Modifier.weight(1f)
                )

                // Tab 3: Quick Consult (Center elevated action)
                QuickConsultCenterButton(
                    isSelected = selectedTab == TabItem.QUICK_CONSULT,
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.CONTEXT_CLICK)
                        onTabSelected(TabItem.QUICK_CONSULT)
                    },
                    modifier = Modifier.weight(1.15f)
                )

                // Tab 4: Book Consultation
                TabButton(
                    tab = TabItem.CONSULT,
                    isSelected = selectedTab == TabItem.CONSULT,
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                        onTabSelected(TabItem.CONSULT)
                    },
                    modifier = Modifier.weight(1f)
                )

                // Tab 5: Profile
                TabButton(
                    tab = TabItem.PROFILE,
                    isSelected = selectedTab == TabItem.PROFILE,
                    onClick = {
                        view.performHapticFeedback(HapticFeedbackConstants.KEYBOARD_TAP)
                        onTabSelected(TabItem.PROFILE)
                    },
                    modifier = Modifier.weight(1f)
                )
            }
        }
    }
}

@Composable
private fun TabButton(
    tab: TabItem,
    isSelected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val interactionSource = remember { MutableInteractionSource() }
    val color = if (isSelected) TealPrimary else InactiveGray

    Column(
        modifier = modifier
            .clickable(interactionSource = interactionSource, indication = null) { onClick() }
            .padding(vertical = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(
            imageVector = tab.icon,
            contentDescription = tab.title,
            tint = color,
            modifier = Modifier.size(22.dp)
        )
        Spacer(modifier = Modifier.height(3.dp))
        Text(
            text = tab.title,
            fontSize = 11.sp,
            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Medium,
            color = color
        )
    }
}

@Composable
private fun QuickConsultCenterButton(
    isSelected: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val interactionSource = remember { MutableInteractionSource() }

    Column(
        modifier = modifier
            .clickable(interactionSource = interactionSource, indication = null) { onClick() }
            .offset(y = (-6).dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Box(
            modifier = Modifier
                .size(44.dp)
                .shadow(elevation = 6.dp, shape = CircleShape, spotColor = TealPrimary.copy(alpha = 0.4f))
                .clip(CircleShape)
                .background(
                    Brush.verticalGradient(
                        colors = listOf(TealPrimary, TealDark)
                    )
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = TabItem.QUICK_CONSULT.icon,
                contentDescription = "Quick Consult",
                tint = Color.White,
                modifier = Modifier.size(24.dp)
            )
        }
        Spacer(modifier = Modifier.height(2.dp))
        Text(
            text = "Quick Consult",
            fontSize = 10.5.sp,
            fontWeight = if (isSelected) FontWeight.Bold else FontWeight.SemiBold,
            color = if (isSelected) TealPrimary else InactiveGray
        )
    }
}
