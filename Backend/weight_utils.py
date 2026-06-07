from Backend.configurations import OPTIMIZATION_WEIGHTS


class WeightUtilities:
    def _get_weights(self) -> object:
        """Resolve or apply optimization weight values.
        """
        optimization = self.scenario.get("optimization", {})

        use_scenario_weights = optimization.get(
            "consider_individual_scenario_weight",
            False,
        )

        weights = dict(OPTIMIZATION_WEIGHTS)

        if use_scenario_weights:
            scenario_weights = optimization.get("weights", {})
            self._validate_weight_keys(scenario_weights, "scenario")
            weights.update(scenario_weights)

        if self.ui_weights:
            self._validate_weight_keys(self.ui_weights, "UI")
            weights.update(self.ui_weights)

        self._validate_weights(weights)

        return {
            weight_key: float(weight_value)
            for weight_key, weight_value in weights.items()
        }

    def _validate_weight_keys(self, weights, source_name) -> None:
        """Validate input data before optimization.
        
        Args:
            weights (_type_): Weights used by this function.
            source_name (_type_): Source name used by this function.
        """
        unknown_weight_keys = set(weights) - set(OPTIMIZATION_WEIGHTS)

        if unknown_weight_keys:
            raise ValueError(
                f"{source_name} contains unknown optimization weight(s): "
                f"{sorted(unknown_weight_keys)}. "
                "Add the weight to OPTIMIZATION_WEIGHTS first if it should be configurable."
            )

    def _validate_weights(self, weights) -> None:
        """Validate input data before optimization.
        
        Args:
            weights (_type_): Weights used by this function.
        """
        for weight_key, weight_value in weights.items():
            if float(weight_value) < 0:
                raise ValueError(
                    f"Optimization weight cannot be negative: {weight_key}"
                )

    def _weight(self, weight_name, default_value=0) -> int:
        """Resolve or apply optimization weight values.
        
        Args:
            weight_name (str): Name of the optimization weight.
            default_value (_type_, optional): Default value used by this function. Defaults to 0.
        """
        return int(
            round(self.weights.get(weight_name, default_value) * 100)
        )
