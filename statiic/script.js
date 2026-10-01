document.addEventListener("DOMContentLoaded", function () {

    const timer = document.getElementById("timer");

    if (timer) {

        let seconds = 60 * 60;

        setInterval(function () {

            if (seconds <= 0) {
                timer.innerText = "00:00";
                return;
            }

            seconds--;

            let minutes = Math.floor(seconds / 60);
            let remaining = seconds % 60;

            timer.innerText =
                String(minutes).padStart(2, "0") +
                ":" +
                String(remaining).padStart(2, "0");

        }, 1000);
    }

});