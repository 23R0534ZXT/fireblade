using System.ComponentModel;
using System.Globalization;
public sealed class FixtureReader {
 public BindingList<FixtureRow> DataList {get;}=[];
 public string FileDescription=>"Fireblade QA reader";
 public HashSet<string> ExpectedHeaders {get;}=["Text,Identifier"];
 public void ProcessFile(string path)=>DataList.Add(new FixtureRow {Text=File.ReadAllText(path),Identifier="0001"});
}
public sealed class FixtureRow {public string Text{get;set;}="";public string Identifier{get;set;}="";public bool Flag{get;set;}=true;public DateTime Time{get;set;}=new DateTime(2026,1,1,0,0,0,DateTimeKind.Utc).AddTicks(1);public ulong LargeId{get;set;}=9007199254740993;}
public sealed class FixtureDouble {
 public string Name=>"FixtureDouble";
 public object Evaluate(params object[] values)=>decimal.Parse(values[0].ToString()!,CultureInfo.InvariantCulture)*2;
 public Type ResultType(params Type[] values)=>typeof(decimal);
}
public sealed class FixtureEcho {
 public string Name=>"FixtureEcho";
 public object? Evaluate(params object[] values)=>values[0];
 public Type ResultType(params Type[] values)=>typeof(string);
}

public sealed class FixtureTypes {
 public string Name=>"FixtureTypes";
 public object Evaluate(params object[] values)=>values[0] is DateTime d && d.Ticks==new DateTime(2026,1,1).Ticks+1 && values[1] is ulong id && id==9007199254740993;
 public Type ResultType(params Type[] values)=>typeof(bool);
}

public sealed class FixturePause {
 public string Name=>"FixturePause";
 public object Evaluate(params object[] values) {Thread.Sleep(10000);return "done";}
 public Type ResultType(params Type[] values)=>typeof(string);
}
