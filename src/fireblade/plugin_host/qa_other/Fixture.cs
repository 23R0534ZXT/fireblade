public sealed class FixtureOtherSecret {
 public string Name=>"FixtureOtherSecret";
 public object Evaluate(params object[] values)=>values[0] is FixtureDetails d ? d.ReadSecret() : throw new InvalidOperationException("Typed instance from reader DLL required");
 public Type ResultType(params Type[] values)=>typeof(int);
}
